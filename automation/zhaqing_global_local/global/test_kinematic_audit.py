import unittest  # 用解析运动场核对真实生产审计的接受和拒绝路径。
import numpy as np  # 构造带非零刚臂转动的六自由度场。
from kinematic_audit import rigid_kinematic_audit  # 直接测试生产函数，不复制其实现。


class KinematicAuditTests(unittest.TestCase):  # 检查不能仅凭力平衡接受错误约束场。
    def setUp(self):  # 每项检查使用同一个100毫米偏心刚臂。
        self.model = {'nodes': {1: np.zeros(3), 2: np.array([0., 100., 0.])}, 'rigid_connections': [{'master': 1, 'slave': 2}]}  # 主从节点按原点和横向偏心设置。
        self.field = np.array([[1., 2., 3., 0., 0., .01], [0., 2., 3., 0., 0., .01]])  # 绕z轴0.01弧度产生从节点负x向1毫米位移。

    def test_accepts_exact_nonzero_rigid_motion(self):  # 位移、速度和加速度均满足同一线性关系时通过。
        self.assertTrue(rigid_kinematic_audit(self.model, [1, 2], self.field, 2*self.field, 3*self.field)['passed'])  # 非零缩放可覆盖三种运动量。

    def test_rejects_balanced_but_incompatible_displacement(self):  # 平衡审计以外的毫米级约束错误必须独立拒绝。
        self.field[1, 0] += .02  # 注入0.02毫米平动相容性错误，不涉及任何力阈值。
        result = rigid_kinematic_audit(self.model, [1, 2], self.field)  # 读取实际审计结果。
        self.assertFalse(result['passed'])  # 错误状态不能成为有效初始场。
        self.assertAlmostEqual(result['fields']['displacement']['translation_max'], .02)  # 检查实际记录的误差大小和单位。

    def test_rejects_acceleration_only_error(self):  # 防止只检查位移而漏掉动力约束错误。
        acceleration = self.field.copy()  # 从一个完全相容的加速度场开始。
        acceleration[1, 4] += .001  # 注入0.001弧度每平方秒的转动加速度错误。
        self.assertFalse(rigid_kinematic_audit(self.model, [1, 2], self.field, self.field, acceleration)['passed'])  # 任一运动量不相容都拒绝。

    def test_rejects_nonfinite_field(self):  # NaN不能借比较运算绕过相容性要求。
        self.field[1, 0] = np.nan  # 构造非有限位移输入。
        with self.assertRaises(ValueError):  # 无效原始场必须产生可追踪的错误。
            rigid_kinematic_audit(self.model, [1, 2], self.field)  # 执行真实输入检查。


if __name__ == '__main__':  # 只在明确执行脚本时运行解析回归。
    unittest.main()  # 返回标准测试退出码，任一断言失败均使验证失败。
