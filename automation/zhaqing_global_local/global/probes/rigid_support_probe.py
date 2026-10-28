import json  # 输出原生小模型的可复现对照证据。
from pathlib import Path  # 定位与生产相同的相容性审计模块。
import sys  # 显式加载上一级生产模块。
import numpy as np  # 保存原生六自由度运动量。
import openseespy.opensees as ops  # 执行真实OpenSees方程，不模拟求解结果。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 只添加本仓库global目录。
from kinematic_audit import rigid_kinematic_audit  # 使用真实生产相容性检查。


def run(handler):  # 输入约束处理方法；返回部分受约束主节点的静力及动力相容性证据。
    ops.wipe()  # 每个处理方法都从独立零状态模型开始。
    ops.model('basic', '-ndm', 3, '-ndf', 6)  # 采用毫米、牛顿、秒的三维六自由度模型。
    coordinates = {1: np.array([0., 0., 0.]), 2: np.array([1000., 0., 0.]), 3: np.array([1000., 100., 0.])}  # 一千毫米梁加一百毫米横向刚臂。
    for node, xyz in coordinates.items():  # 建立全部三个物理节点。
        ops.node(node, *xyz)  # 原生输入使用毫米坐标。
    ops.fix(1, 1, 1, 1, 1, 1, 1)  # 梁根部完全固定。
    ops.fix(2, 0, 1, 1, 0, 0, 0)  # 保留节点仅约束y/z平动，模拟全桥滚动支座与刚臂并存。
    ops.geomTransf('Linear', 1, 0., 0., 1.)  # 梁局部轴采用全局z参考向量。
    ops.element('elasticBeamColumn', 1, 1, 2, 1000., 206000., 79230., 100000., 100000., 100000., 1)  # 单元1连节点1/2；A=1000mm²，E=206000、G=79230N/mm²，J=Iy=Iz=100000mm⁴，采用变换1；这些是排除壳影响的弹性对照参数。
    ops.rigidLink('beam', 2, 3)  # 从节点遵循保留节点的六自由度刚臂关系。
    for node in (2, 3):  # 两端均保留真实平动质量以进行动力对照。
        ops.mass(node, .1, .1, .1, 0., 0., 0.)  # 每节点0.1吨，旋转质量为零。
    ops.timeSeries('Linear', 1)  # 静力荷载系数随伪时间增长。
    ops.pattern('Plain', 1, 1)  # 建立独立荷载模式。
    ops.load(3, 100., 0., 0., 0., 0., 0.)  # 从节点施加100牛顿x向力，同时产生z向弯矩。
    if handler == 'Lagrange':  # 对照方法直接保留约束方程，避免Transformation受约束主节点分支。
        ops.constraints(handler, 1., 1.)  # 单位乘子缩放用于微型对照，不作为全桥推荐参数。
    else:  # 原工程使用的Transformation处理方法。
        ops.constraints(handler)  # 不改变原生处理方法的实现。
    ops.numberer('RCM')  # 真实方程重排，避免依赖节点编号次序。
    ops.system('UmfPack')  # 使用支持不定矩阵的通用稀疏直接解法。
    ops.test('NormUnbalance', 1.e-8, 40, 0)  # 微型模型采用1e-8混合N/Nmm残差阈值、最多40次迭代、打印级别0；不改变全桥0.02N门槛。
    ops.algorithm('Newton')  # 使用标准Newton，排除线搜索影响。
    ops.integrator('LoadControl', 1.)  # 一步施加完整静力荷载。
    ops.analysis('Static')  # 执行真实静力分析。
    code = ops.analyze(1)  # 获取原生返回码。
    assert code == 0, (handler, code)  # 原生失败不得被隐藏。
    model = {'nodes': coordinates, 'rigid_connections': [{'master': 2, 'slave': 3}]}  # 与原生一致的独立刚臂声明。
    nodes = list(coordinates)  # 固定节点场顺序。
    first_static = rigid_kinematic_audit(model, nodes, np.asarray([ops.nodeDisp(node) for node in nodes]))  # 区分首次加载与随后零荷载增量清理的约束表现。
    ops.integrator('LoadControl', 0.)  # 与全桥相同，在不改变外载下执行下一次静力清理。
    code = ops.analyze(1)  # 触发真实的下一增量约束处理。
    assert code == 0, (handler, 'cleanup', code)  # 原生失败直接保留为失败。
    displacement = np.asarray([ops.nodeDisp(node) for node in nodes])  # 读取真实提交后位移。
    static = rigid_kinematic_audit(model, nodes, displacement)  # 单独检查静力约束是否成立。
    ops.loadConst('-time', 0.)  # 保持静力荷载，并将动力时钟归零。
    ops.wipeAnalysis()  # 按全桥流程重新创建动力分析对象。
    if handler == 'Lagrange':  # 对照保持同一约束处理方法。
        ops.constraints(handler, 1., 1.)  # 小模型对照沿用静力乘子缩放。
    else:  # 原全桥重新建立Transformation处理器。
        ops.constraints(handler)  # 不对节点状态施加后处理投影。
    ops.numberer('RCM')  # 动力方程同样使用原生重排。
    ops.system('UmfPack')  # 对照继续使用同一稀疏解法。
    ops.test('NormUnbalance', 1.e-8, 40, 0)  # 动力对照仍采用1e-8混合N/Nmm阈值、最多40次迭代、打印级别0，与静力要求相同。
    ops.algorithm('Newton')  # 排除额外算法差异。
    ops.integrator('Newmark', .5, .25)  # 与全桥相同的平均加速度积分。
    ops.analysis('Transient')  # 从真实静力状态开始动力分析。
    code = ops.analyze(2, .003125)  # 推进两个原生子步，覆盖全桥一个导出帧。
    assert code == 0, (handler, code)  # 保留真实动力返回码。
    fields = [np.asarray([reader(node) for node in nodes]) for reader in (ops.nodeDisp, ops.nodeVel, ops.nodeAccel)]  # 读取全部原生运动场。
    dynamic = rigid_kinematic_audit(model, nodes, *fields)  # 三种运动场必须满足同一刚臂变换。
    return {'handler': handler, 'first_static': first_static, 'static': static, 'dynamic': dynamic, 'static_displacement': displacement.tolist(), 'dynamic_displacement': fields[0].tolist()}  # 区分首次加载、零增量清理和真实动力阶段，结果仅属于三节点对照。


if __name__ == '__main__':  # 仅显式调用时运行原生对照。
    results = [run(handler) for handler in ('Transformation', 'Lagrange')]  # 同一模型比较原方法与精确乘子对照。
    print(json.dumps({'scope': 'NATIVE_THREE_NODE_CONSTRAINT_DIAGNOSTIC_NOT_FULL_BRIDGE', 'opensees_version': ops.version(), 'results': results}, indent=2, allow_nan=False))  # 保留全部原生数值及严格限定的验证范围。
    assert not results[0]['static']['passed'] and not results[0]['dynamic']['passed'], 'Expected native 3.8 Transformation regression was not reproduced'  # 固定版本应真实复现受约束主节点问题。
    assert results[1]['static']['passed'] and results[1]['dynamic']['passed'], 'Lagrange control failed'  # 微型对照只证明约束可正确实现，不宣称全桥替代已合格。
