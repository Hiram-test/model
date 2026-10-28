#!/usr/bin/env python3
# 本脚本比较真实单壳单元的牛顿末次方程与提交后动力平衡；不构成全桥认证。
import json  # 用严格 JSON 输出可重现的数值证据。
import hashlib  # 将实际执行脚本和生产审计文件绑定到原生结果回执。
import importlib.metadata  # 保存实际安装的软件版本，检查与Actions的环境一致性。
import platform  # 记录操作系统与内核，避免将WSL误称为原Actions宿主。
import sys  # 显式加入父级模块路径并在真实原生失败时返回非零状态。
from pathlib import Path  # 根据当前脚本位置查找实际生产动力审计函数。
import numpy as np  # 保存六自由度向量并计算力残差，平移单位为毫米。
import openseespy.opensees as ops  # 调用与 Actions 相同版本的原生有限元后端。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 将global目录加入导入路径，不依赖调用者工作目录。
from transient_cases import dynamic_balance  # 直接回归生产独立审计函数，避免仅测试另一个同名实现。


def probe(element, dt, native_test='NormUnbalance'):  # 输入壳公式、秒制步长和明确的内部判据；返回完整0.2s原生记录。
    ops.wipe()  # 清除上一个单元试验的状态，避免两个对照互相影响。
    ops.model('basic', '-ndm', 3, '-ndf', 6)  # 建立三维、每节点六自由度的毫米牛顿秒模型。
    coordinates = [(0., 0., 0.), (1000., 0., 0.), (1000., 1000., 0.), (0., 1000., 0.)]  # 定义边长一千毫米的逆时针正方形壳。
    for node, xyz in enumerate(coordinates, 1):  # 原生节点编号从一开始，与四节点壳连接顺序一致。
        ops.node(node, *xyz)  # 写入对应的三维毫米坐标。
        ops.mass(node, .1, .1, .1, 0., 0., 0.)  # 各平移自由度质量为零点一吨，转动不设置虚拟质量。
    for node in (1, 2):  # 固定一条边的两个节点形成稳定悬臂壳。
        ops.fix(node, 1, 1, 1, 1, 1, 1)  # 六自由度固定，数值一表示该自由度受到约束。
    ops.section('ElasticMembranePlateSection', 1, 206000., .3, 10., 0.)  # 定义钢弹性模量牛顿每平方毫米、泊松比、十毫米厚度和零单元密度。
    options = ('-corotational',) if element == 'ASDShellQ4' else ()  # ASDShellQ4必须显式启用共旋几何非线性，NLDKGQ采用自身非线性公式。
    ops.element(element, 1, 1, 2, 3, 4, 1, *options)  # 以同一截面建立指定类型的真实四节点非线性壳。
    ops.timeSeries('Linear', 1)  # 使用荷载系数等于秒数的时间函数，避免初始冲击。
    ops.pattern('Plain', 1, 1)  # 绑定一个外荷载模式，整个试验内不改变模式定义。
    for node in (3, 4):  # 对悬臂自由端施加对称面外弯曲荷载。
        ops.load(node, 0., 0., -10000., 0., 0., 0.)  # 在一秒时每个节点达到一万牛顿向下力，产生可测几何更新。
    ops.constraints('Transformation')  # 消去固定自由度，保留原生独立方程。
    ops.numberer('RCM')  # 使用确定性的反向带宽排序。
    ops.system('BandGeneral')  # 小型模型采用通用带状求解器，无需额外并行依赖。
    native_tolerance=1e-5 if native_test=='NormUnbalance' else 1e-8  # 力模式用1e-5混合N/Nmm，位移模式用1e-8混合mm/rad，仅用于内部迭代停止。
    ops.test(native_test, native_tolerance, 120, 0)  # 最多120次迭代，结束后仍须通过独立物理审计。
    ops.algorithm('NewtonLineSearch', .8)  # 与全桥一致地使用八成线搜索参数。
    ops.integrator('Newmark', .5, .25)  # 使用平均加速度格式，参数分别为 gamma 和 beta。
    ops.rayleigh(.02, 0., 0., 0.)  # 仅设置每秒零点零二的质量比例阻尼。
    ops.analysis('Transient')  # 建立真实隐式动力分析，不采用静力替代。
    records = []  # 保存每个提交后状态的原生与独立残差证据。
    model = {'nodes': {node: np.asarray(xyz) for node, xyz in enumerate(coordinates, 1)}, 'elements': {1: ('DECK_PLATES', [1, 2, 3, 4])}, 'mass': {node: .1 for node in range(1, 5)}, 'gravity': {node: np.zeros(6) for node in range(1, 5)}, 'fixities': {node: [int(node <= 2)] * 6 for node in range(1, 5)}}  # 构造与生产审计相同的数据契约，全部质量为吨且恒载为零。
    for step in range(1, round(.2 / dt) + 1):  # 各步长均执行完整零点二秒，避免通过缩短时程降低残差。
        previous_displacement = np.asarray([ops.nodeDisp(node) for node in range(1, 5)])  # 保存前一步毫米及弧度位移，用于独立核验Newmark运动学。
        previous_velocity = np.asarray([ops.nodeVel(node) for node in range(1, 5)])  # 保存前一步毫米每秒及弧度每秒速度。
        previous_acceleration = np.asarray([ops.nodeAccel(node) for node in range(1, 5)])  # 保存前一步毫米每秒平方及弧度每秒平方加速度。
        code = ops.analyze(1, dt)  # 按输入步长推进一次真实积分，并完成原生提交。
        if code != 0:  # 失败状态可能没有有效收敛历史，必须先保存实际退出码。
            records.append({'step': step, 'exit_code': code, 'dt_s': dt})  # 记录失败的真实步号及时间步长，避免查询异常覆盖失败证据。
            break  # 停止当前单元算例，不读取未被接受的力学状态。
        iterations = ops.testIter()  # 记录实际执行迭代次数，定位有效范数条目。
        last_norm = ops.testNorm()[iterations - 1]  # 选取末次真实迭代的原始范数，单位由native_test确定。
        first = np.asarray(ops.eleForce(1), dtype=float).reshape(4, 6)  # 获取提交后第一次全局抵抗力，单位为牛顿及牛顿毫米。
        second = np.asarray(ops.eleForce(1), dtype=float).reshape(4, 6)  # 重复调用用于检测抵抗力查询是否带有副作用。
        rhs = np.asarray(ops.printB('-ret'), dtype=float)  # 此命令调用formUnbalance重组提交后右端项，不能解释为提交前缓存。
        after_rhs = np.asarray(ops.eleForce(1), dtype=float).reshape(4, 6)  # 检查printB重新组装是否改变再次查询的单元抵抗力。
        residual = first.copy()  # 独立平衡从单元抵抗力开始，不读取原生反力构造。
        for node in range(1, 5):  # 四个节点均计算完整六自由度动力方程。
            residual[node - 1, :3] += .1 * (np.asarray(ops.nodeAccel(node)[:3]) + .02 * np.asarray(ops.nodeVel(node)[:3]))  # 加入吨毫米每秒平方惯性与质量阻尼，对应牛顿。
        residual[2:, 2] += 10000. * ops.getTime()  # 减去自由端负向外力，使用真实提交后的秒数计算荷载系数。
        mapped = np.zeros_like(residual)  # 将独立方程右端项映射回物理节点，固定自由度保持零。
        for node in (3, 4):  # 仅映射十二个自由端自由度，固定反力不参与范数。
            mapped[node - 1] = rhs[np.asarray(ops.nodeDOFs(node), dtype=int)]  # 根据原生方程编号取值，避免假设排序。
        ops.reactions('-dynamic')  # 请求包含惯性和阻尼的原生动力反力，用于独立组装交叉检查。
        reactions = np.asarray([ops.nodeReaction(node) for node in range(1, 5)])  # 保存全部节点六自由度原生反力。
        displacement = np.asarray([ops.nodeDisp(node) for node in range(1, 5)])  # 读取本步提交位移，不人为投影或修正。
        velocity = np.asarray([ops.nodeVel(node) for node in range(1, 5)])  # 读取本步提交速度，保持原生双精度值。
        acceleration = np.asarray([ops.nodeAccel(node) for node in range(1, 5)])  # 读取本步提交加速度，避免由运动学公式替换真实输出。
        displacement_error = displacement - previous_displacement - dt * previous_velocity - .25 * dt**2 * (previous_acceleration + acceleration)  # 核验beta等于四分之一的Newmark位移恒等式。
        velocity_error = velocity - previous_velocity - .5 * dt * (previous_acceleration + acceleration)  # 核验gamma等于二分之一的Newmark速度恒等式。
        applied = np.zeros((4, 6))  # 创建实际外力数组，未施加的方向保持零牛顿或零牛顿毫米。
        applied[2:, 2] = -10000. * ops.getTime()  # 两个自由端节点的实际竖向荷载与原生时间函数完全一致。
        production_residual, production_audit = dynamic_balance(model, [1, 2, 3, 4], {node: node - 1 for node in range(1, 5)}, applied, .02, native_test, native_tolerance)  # 真实生产审计记录实际内部判据，并独立核验力与RHS。
        records.append({'step': step, 'exit_code': code, 'dt_s': dt, 'native_last_norm_mixed': last_norm, 'postcommit_reassembled_rhs_norm_mixed': float(np.linalg.norm(rhs)), 'postcommit_free_force_N': float(np.max(np.abs(residual[2:, :3]))), 'postcommit_free_moment_Nmm': float(np.max(np.abs(residual[2:, 3:]))), 'postcommit_plus_rhs_max_mixed': float(np.max(np.abs((residual + mapped)[2:]))), 'repeat_eleForce_change_mixed': float(np.max(np.abs(first - second))), 'printB_eleForce_change_mixed': float(np.max(np.abs(first - after_rhs))), 'independent_native_difference_mixed': float(np.max(np.abs(residual - reactions)))})  # 保存收敛前范数与提交后残差、查询副作用及组装一致性，混合单位不能代替物理门槛。
        records[-1].update(newmark_translation_identity_max_mm=float(np.max(np.abs(displacement_error[:, :3]))), newmark_rotation_identity_max_rad=float(np.max(np.abs(displacement_error[:, 3:]))), newmark_velocity_identity_max_mm_s=float(np.max(np.abs(velocity_error[:, :3]))), newmark_angular_velocity_identity_max_rad_s=float(np.max(np.abs(velocity_error[:, 3:]))))  # 将平动、转动及对应速度分开记录，保留明确物理单位且不改变验收门槛。
        records[-1].update(production_residual_equivalent_N=production_residual, production_rhs_agreement_equivalent_N=production_audit['postcommit_rhs_agreement_equivalent_N'])  # 保留真实生产函数给出的等效牛顿残差与方程交叉校核差。
        records[-1].update(native_test_type=native_test,native_test_norm_units='mixed_N_Nmm' if native_test=='NormUnbalance' else 'mixed_mm_rad')  # 明确区分力和位移停止证据，禁止混用单位。
        direct_equivalent = max(float(np.max(np.abs(residual[2:, :3]))), float(np.max(np.abs(residual[2:, 3:]))) / 5500.)  # 使用与生产相同的五千五百毫米参考长度，将直接力矩转换为等效牛顿。
        records[-1]['production_direct_difference_equivalent_N'] = abs(production_residual - direct_equivalent)  # 保存生产审计与独立直接计算之间的量纲一致差值。
        for key in ('newmark_translation_identity_max_mm', 'newmark_rotation_identity_max_rad', 'newmark_velocity_identity_max_mm_s', 'newmark_angular_velocity_identity_max_rad_s'):  # 分别核验四种明确单位的Newmark恒等式。
            assert records[-1][key] <= 1.e-9, (element, dt, step, key, records[-1][key])  # 固定一乘十负九的运动学一致性界限，来源为双精度数值回归要求。
        for key in ('repeat_eleForce_change_mixed', 'printB_eleForce_change_mixed', 'postcommit_plus_rhs_max_mixed', 'independent_native_difference_mixed', 'production_direct_difference_equivalent_N'):  # 核验无副作用查询及两条独立物理组装路径。
            assert records[-1][key] <= 1.e-7, (element, dt, step, key, records[-1][key])  # 固定一乘十负七的数值一致性容差，不将观测峰值反设为门槛。
    return records  # 返回真实原生试验记录，不生成虚拟成功结论。


def rigid_arm_probe():  # 用真实Transformation验证偏心刚臂从节点质量及荷载的T转置组装。
    ops.wipe()  # 与壳试验分离原生模型及时间状态。
    ops.model('basic', '-ndm', 3, '-ndf', 6)  # 采用三维六自由度牛顿毫米秒体系。
    coordinates = {1: np.array([0., 0., 0.]), 2: np.array([1000., 0., 0.]), 3: np.array([1000., 100., 0.])}  # 梁长一千毫米，刚臂偏心一百毫米。
    for node, xyz in coordinates.items():  # 建立支点、保留节点及从节点三个物理位置。
        ops.node(node, *xyz)  # 输入物理节点毫米坐标。
    ops.fix(1, 1, 1, 1, 1, 1, 1)  # 梁根部完全固定。
    ops.geomTransf('Linear', 1, 0., 0., 1.)  # 使用线弹性梁局部坐标，参考向量沿全局竖向。
    ops.element('elasticBeamColumn', 1, 1, 2, 1000., 206000., 79230., 100000., 100000., 100000., 1)  # 指定毫米面积及四次方惯性，模量单位牛顿每平方毫米。
    ops.rigidLink('beam', 2, 3)  # 以节点二保留节点三的平动及旋转兼容性。
    for node, mass in ((2, .1), (3, .2)):  # 在保留节点与从节点分别设置零点一吨及零点二吨质量。
        ops.mass(node, mass, mass, mass, 0., 0., 0.)  # 仅平动质量，刚臂变换自然引入等效转动惯性。
    ops.timeSeries('Linear', 1)  # 保持可预测的线性时间荷载。
    ops.pattern('Plain', 1, 1)  # 使用单一明确的荷载模式。
    ops.load(3, 0., 0., -100., 0., 0., 0.)  # 在偏心从节点施加每秒一百牛顿负竖向荷载。
    ops.constraints('Transformation')  # 使用与全桥相同的约束消元方法。
    ops.numberer('RCM')  # 显式重排方程以测试nodeDOFs真实映射。
    ops.system('BandGeneral')  # 小模型使用通用带状解法。
    ops.test('NormUnbalance', 1.e-5, 120, 0)  # 微型方程采用与壳探针相同的数值停止界限。
    ops.algorithm('Newton')  # 弹性梁采用标准牛顿迭代。
    ops.integrator('Newmark', .5, .25)  # 使用平均加速度时间积分。
    ops.rayleigh(.02, 0., 0., 0.)  # 声明与独立审计相同的质量阻尼系数。
    ops.analysis('Transient')  # 建立真实动力分析。
    model = {'nodes': coordinates, 'elements': {1: ('BEAM', [1, 2])}, 'mass': {1: 0., 2: .1, 3: .2}, 'gravity': {node: np.zeros(6) for node in coordinates}, 'fixities': {1: [1] * 6, 2: [0] * 6, 3: [1] * 6}, 'rigid_connections': [{'master': 2, 'slave': 3}]}  # 从节点在独立方程掩码中排除，其物理力通过刚臂T转置保留。
    records = []  # 保存四个真实微型动力步的审计结果。
    for step in range(1, 5):  # 四步足以验证非零位移、速度、加速度和偏心荷载。
        code = ops.analyze(1, .003125)  # 使用与全桥两子步设置相同的秒制积分间隔。
        assert code == 0, ('rigid_arm_native_failure', step, code)  # 原生失败直接导致非零回归退出，禁止伪造成功。
        applied = np.zeros((3, 6))  # 初始化全物理节点的外荷载。
        applied[2, 2] = -100. * ops.getTime()  # 记录从节点真实竖向时间荷载。
        residual, audit = dynamic_balance(model, [1, 2, 3], {1: 0, 2: 1, 3: 2}, applied, .02)  # 真实生产函数校验MPC惯性、反力及原生方程编号。
        records.append({'step': step, 'residual_equivalent_N': residual, **audit})  # 保存原始物理审计及真实刚臂热点。
        assert audit['postcommit_rhs_agreement_equivalent_N'] <= 1.e-7, audit  # 固定严格数值一致性要求，检查T转置和方程映射。
    return records  # 返回真实刚臂测试证据。


if __name__ == '__main__':  # 仅在显式执行此文件时运行微型原生试验。
    result = {element + '_dt_' + str(dt): probe(element, dt) for element in ('ShellNLDKGQ', 'ASDShellQ4') for dt in (.003125, .0015625, .00078125)}  # 对应全桥输出间隔零点零零六二五秒内的二、四、八子步，均完成零点二秒。
    result.update({f'ASDShellQ4_NormDispIncr_dt_{dt}':probe('ASDShellQ4',dt,'NormDispIncr') for dt in (.003125,.0015625)})  # 补充位移停止模式下两个真实步长的完整原生回归。
    summaries = {name: {key: max(row[key] for row in rows if key in row) for key in rows[0] if key not in ('step', 'exit_code', 'dt_s','native_test_type','native_test_norm_units')} for name, rows in result.items()}  # 只汇总数值指标，判据名称和单位保留在逐步原始记录中。
    failures = [name for name, rows in result.items() if any(row['exit_code'] != 0 for row in rows)]  # 任何原生步骤失败均判定该微型回归执行失败。
    versions = {package: importlib.metadata.version(package) for package in ('numpy', 'scipy', 'h5py', 'openseespy', 'openseespylinux')}  # 记录实际依赖版本以核实Actions复现环境。
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (Path(__file__), Path(__file__).resolve().parents[1] / 'transient_cases.py')}  # 保存本脚本和实际生产审计文件的SHA256；用于核实证据与交付代码完全对应。
    print(json.dumps({'scope': 'NATIVE_SINGLE_SHELL_DIAGNOSTIC_NOT_BRIDGE_QUALIFICATION', 'opensees_version': ops.version(), 'python_version': sys.version, 'platform': platform.platform(), 'runtime_versions': versions, 'source_sha256': source_hashes, 'native_failures': failures, 'summary_max': summaries, 'results': result, 'rigid_arm_results': rigid_arm_probe()}, allow_nan=False))  # 输出有限数值、环境、源码哈希、真实刚臂结果及失败情况，不宣称全桥通过。
    sys.exit(1 if failures else 0)  # 只有全部原生微型算例完成才正常返回，不把失败吞掉作为成功。
