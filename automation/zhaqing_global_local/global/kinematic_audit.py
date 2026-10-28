import argparse  # 提供直接审计已下载全桥预平衡工件的命令行。
import json  # 读取模型契约并保存可核验结果。
from pathlib import Path  # 将所有读写限制在指定预平衡目录。
import sys  # 用非零退出码明确传播相容性拒绝。
import numpy as np  # 用双精度数组核对原始节点运动，不投影或修改求解状态。


def rigid_kinematic_audit(model, nodes, displacement, velocity=None, acceleration=None):  # 输入完整模型、节点序列及原生运动场；返回全部声明刚臂的相容性证据。
    lookup = {node: row for row, node in enumerate(nodes)}  # 将实际节点号映射到输入场行号。
    connections = model.get('rigid_connections', [])  # 没有声明刚臂的模型返回零条受检约束。
    fields = [('displacement', displacement, 'mm', 'rad')]  # 位移前后三列分别使用毫米和弧度。
    if velocity is not None:  # 动力状态同时验证速度约束。
        fields.append(('velocity', velocity, 'mm_s', 'rad_s'))  # 速度单位为毫米每秒和弧度每秒。
    if acceleration is not None:  # 动力状态同时验证加速度约束。
        fields.append(('acceleration', acceleration, 'mm_s2', 'rad_s2'))  # 加速度单位为毫米每平方秒和弧度每平方秒。
    result = {'passed': True, 'connections_checked': len(connections), 'translation_tolerance': 1.e-7, 'rotation_tolerance': 1.e-10, 'fields': {}}  # 阈值用于双精度线性约束恒等式，绝不代替或放宽力平衡门槛。
    for name, field, translation_unit, rotation_unit in fields:  # 每种原生运动量使用同一个已声明的线性刚臂关系。
        values = np.asarray(field, dtype=float)  # 只读转换数组，不修正从节点结果。
        if values.shape != (len(nodes), 6) or not np.isfinite(values).all():  # 完整六自由度有限场是审计前提。
            raise ValueError('Rigid kinematic audit requires complete finite six-component fields')  # 缺失或无效场不能被认定为相容。
        translation_max, rotation_max, hotspot = 0., 0., None  # 分别累计平动、转动最大误差及控制约束。
        for connection in connections:  # 检查全部刚臂，禁止仅抽取稳定节点。
            master, slave = connection['master'], connection['slave']  # 读取该约束真实主从节点号。
            retained, dependent = values[lookup[master]], values[lookup[slave]]  # 读取未修改的两端原生值。
            arm = np.asarray(model['nodes'][slave]) - np.asarray(model['nodes'][master])  # 参考臂使用建模坐标，单位毫米。
            error_translation = dependent[:3] - retained[:3] - np.cross(retained[3:], arm)  # 刚臂线性关系为u从=u主+转角叉乘参考臂。
            error_rotation = dependent[3:] - retained[3:]  # 梁型刚臂三转角必须相等。
            translation = float(np.max(np.abs(error_translation)))  # 保存该约束最大平动误差，单位由当前场确定。
            rotation = float(np.max(np.abs(error_rotation)))  # 保存该约束最大转动误差，避免混合不同单位。
            if translation > translation_max or rotation > rotation_max:  # 任一分量创新高时保留可定位原始证据。
                hotspot = {'master': master, 'slave': slave, 'translation_error': error_translation.tolist(), 'rotation_error': error_rotation.tolist()}  # 保存完整带符号误差，不作后处理平滑。
            translation_max, rotation_max = max(translation_max, translation), max(rotation_max, rotation)  # 分别取全部刚臂的最大值。
        passed = translation_max <= 1.e-7 and rotation_max <= 1.e-10  # 仅允许双精度运动恒等式误差，不接受毫米级约束漂移。
        result['fields'][name] = {'translation_max': translation_max, 'translation_unit': translation_unit, 'rotation_max': rotation_max, 'rotation_unit': rotation_unit, 'hotspot': hotspot, 'passed': passed}  # 输出各场独立单位、位置和判定。
        result['passed'] = result['passed'] and passed  # 所有受检运动量都相容才通过。
    return result  # 返回完整证据，调用者负责保留失败并拒绝后续发布。


if __name__ == '__main__':  # 明确调用才执行已保存工件审计，不触发全桥重算。
    parser = argparse.ArgumentParser()  # 建立已存在预平衡目录的显式输入契约。
    parser.add_argument('--prestate', type=Path, required=True)  # 目录必须含真实mesh_contract.json及equilibrium_fields.npz。
    args = parser.parse_args()  # 读取操作者选定的工件路径。
    contract = json.loads((args.prestate/'mesh_contract.json').read_text(encoding='utf-8'))  # 读取原生模型冻结的全部刚臂及坐标。
    model = {'nodes': {int(key): np.asarray(value) for key, value in contract['nodes'].items()}, 'rigid_connections': contract['rigid_connections']}  # 保留真实节点号和声明约束，不重新建模。
    with np.load(args.prestate/'equilibrium_fields.npz', allow_pickle=False) as data:  # 只读取原始数值数组，禁用对象反序列化。
        report = rigid_kinematic_audit(model, [int(node) for node in data['node_ids']], data['displacement'])  # 全节点检查真实静力位移场。
    (args.prestate/'independent_rigid_kinematics.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')  # 写入独立回执，不覆盖任何原始求解证据。
    print(json.dumps(report, indent=2, allow_nan=False))  # 显示明确单位、误差和主从节点。
    sys.exit(0 if report['passed'] else 1)  # 不相容必须作为失败返回，不能借原生退出零制造成功。
