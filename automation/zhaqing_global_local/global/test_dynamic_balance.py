#!/usr/bin/env python3  # 运行有限数组审计回归；不宣称完成全桥动力验证。
import ast  # 从真实生产文件提取审计函数，避免测试依赖本机原生求解器安装。
from pathlib import Path  # 定位与测试相邻的真实动力实现文件。
from types import SimpleNamespace  # 提供仅包含审计所需接口的可控原生引擎替身。
import unittest  # 使用标准库报告每个独立物理契约的通过或失败。
from unittest.mock import Mock  # 记录原生接口调用并返回人工可核对的物理量。
import numpy as np  # 构造双精度N、Nmm、mm/s和tonne数组。
from kinematic_audit import rigid_kinematic_audit  # 测试生产函数实际使用的运动相容性检查。


class DynamicBalanceTests(unittest.TestCase):  # 测试实际审计代码，不复写其残差算法。
    def setUp(self):  # 每次创建独立函数命名空间和单节点解析模型。
        source=Path(__file__).with_name('transient_cases.py')  # 此路径固定指向生产动力审计实现。
        tree=ast.parse(source.read_text(encoding='utf-8'),filename=str(source))  # 保留实际函数AST以免导入原生求解器。
        names={'assemble_constraint_actions','dynamic_balance'}  # 只提取此次审计及其唯一生产辅助函数。
        selected=ast.Module(body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names],type_ignores=[])  # 排除启动全桥及外部依赖的代码。
        self.ops=SimpleNamespace()  # 替身所有返回值均由各测试的解析物理状态提供。
        namespace={'np':np,'ops':self.ops,'rigid_kinematic_audit':rigid_kinematic_audit}  # 注入真实相容性检查和可控原生接口。
        exec(compile(selected,str(source),'exec'),namespace)  # 编译执行真实函数体，避免镜像实现造成自证。
        self.balance=namespace['dynamic_balance']  # 保存实际被测函数供每个断言调用。
        self.nodes=[101]  # 非零节点号用于发现将节点号误当数组位置的错误。
        self.index={101:0}  # 唯一节点对应数组第零行。
        self.model={'nodes':{101:np.zeros(3)},'elements':{7:('FIXTURE',[101])},'mass':{101:2.},'gravity':{101:np.zeros(6)},'fixities':{101:[0]*6}}  # 2 tonne解析质量和六个独立分量。
        self.applied=np.zeros((1,6))  # 默认零风载N/Nmm，按需在测试中设置。
        self.velocity=np.zeros((1,6))  # 默认零平动和转动速度。
        self.acceleration=np.zeros((1,6))  # 默认零平动和转动加速度。
        self.internal=np.zeros((1,6))  # 默认零原生单元抵抗力。
        self.native=np.zeros((1,6))  # 独立手算的原生提交后节点残差。
        self.rhs=np.zeros(6)  # 独立手算且按原生方程顺序排列的右端项。
        self.equations={101:[5,4,3,2,1,0]}  # 故意逆序模拟RCM方程重排。
        self.ops.eleForce=Mock(side_effect=lambda tag:self.internal.reshape(-1).tolist())  # 返回单个解析单元的完整N/Nmm抵抗力。
        self.ops.nodeVel=Mock(side_effect=lambda node:self.velocity[self.index[node]].tolist())  # 返回指定真实节点的速度。
        self.ops.nodeDisp=Mock(side_effect=lambda node:np.zeros(6).tolist())  # 默认解析模型没有刚臂位移差；专门的相容性测试覆盖非零运动。
        self.ops.nodeAccel=Mock(side_effect=lambda node:self.acceleration[self.index[node]].tolist())  # 返回指定真实节点的加速度。
        self.ops.reactions=Mock()  # 仅记录要求包含动力作用的重组装调用。
        self.ops.nodeReaction=Mock(side_effect=lambda node:self.native[self.index[node]].tolist())  # 返回手算节点残差，不调用被测算法。
        self.ops.testNorm=Mock(return_value=[.005,0.])  # 模拟提交前已满足0.005的原生测试历史。
        self.ops.testIter=Mock(return_value=1)  # 只有第一项历史实际执行。
        self.ops.printB=Mock(side_effect=lambda *args:self.rhs.tolist())  # 模拟提交后重新组装的方程右端项。
        self.ops.nodeDOFs=Mock(side_effect=lambda node:self.equations[node])  # 返回真实方程排列用于验证映射。

    def audit(self):  # 使用固定0.02/s质量比例阻尼调用生产审计。
        return self.balance(self.model,self.nodes,self.index,self.applied,.02)  # 输出独立等效N最大残差和审计字典。

    def test_tonne_mm_units_and_signed_terms(self):  # 用非零五项抵消验证单位、符号和输出证据。
        self.internal[0,1]=3.01  # 横向单元抵抗力为3.01 N，留下可定位的0.01 N残差。
        self.applied[0,1]=1.  # 同向风载为1 N，在残差中应扣除。
        self.model['gravity'][101][1]=4.  # 人工恒载4 N用于独立检查扣除方向。
        self.acceleration[0,1]=.5  # 2 tonne乘0.5 mm/s²给出1 N惯性。
        self.velocity[0,1]=25.  # 2 tonne乘0.02/s乘25 mm/s给出1 N阻尼。
        self.native[0,1]=.01  # 独立手算3.01-1-4+1+1为0.01 N。
        self.rhs[4]=-.01  # 横向方程号4的右端为负0.01 N。
        residual,report=self.audit()  # 五项仅留下已声明的小残差，便于逐项检验。
        self.assertAlmostEqual(residual,.01)  # 若错误乘或除1000，审计必须无法保持解析残差。
        self.assertEqual(report['hotspot_terms_N_or_Nmm'],{'internal':3.01,'negative_wind':-1.,'negative_gravity':-4.,'inertia':1.,'damping':1.})  # 热点必须保留各物理项的量值和符号。
        self.ops.reactions.assert_called_once_with('-dynamic')  # 必须要求惯性和阻尼参与原生残差。
        self.model['mass'][101]=2000.  # 故意将tonne错当kg，制造1000倍量纲错误。
        with self.assertRaisesRegex(RuntimeError,'dynamic balance mismatch'):  # 原生解析基准不变时必须明确拒绝错误质量。
            self.audit()  # 验证错误单位不会被当作合法平衡数据。

    def test_small_native_norm_does_not_hide_failed_physical_gate(self):  # 提交前收敛不能替代提交后0.02 N物理门槛。
        self.internal[0,1]=.020801885  # 使用原诊断量级的横向提交后残差N。
        self.native[0,1]=.020801885  # 原生节点重组装与独立内力完全一致。
        self.rhs[4]=-.020801885  # 横向自由度映射到方程4，右端符号与残差相反。
        residual,report=self.audit()  # 实际执行生产审计而非替身判定逻辑。
        self.assertGreater(residual,.02)  # 原独立门槛仍应拒绝该状态，禁止通过证据字段消除残差。
        self.assertEqual(report['native_last_test_norm_mixed_N_Nmm'],.005)  # 保留不同时间点的原生停止证据。
        self.assertAlmostEqual(report['postcommit_rhs_l2_mixed_N_Nmm'],residual)  # 单非零方程L2应等于其绝对值。
        self.assertEqual(report['postcommit_rhs_agreement_equivalent_N'],0.)  # 正确逆序映射与符号必须严格一致。
        self.assertEqual(report['hotspot_dof_1based'],2)  # 热点按物理自由度报告而非原生方程号。
        self.assertAlmostEqual(sum(report['hotspot_terms_N_or_Nmm'].values()),residual)  # 有符号物理项必须闭合至热点残差。

    def test_displacement_stop_keeps_force_gate_and_correct_units(self):  # 位移停止条件不能替代物理力验收或被错标成力范数。
        self.internal[0,1]=.020801885; self.native[0,1]=.020801885; self.rhs[4]=-.020801885  # 保留原失败量级的力残差夹具。
        self.ops.testNorm.return_value=[5e-10]  # 模拟远低于1e-8位移停止阈值的迭代修正。
        residual,report=self.balance(self.model,self.nodes,self.index,self.applied,.02,'NormDispIncr',1e-8)  # 真实生产审计使用明确的位移判据元数据。
        self.assertGreater(residual,.02)  # 即使位移已收敛，超限力残差仍供上层拒绝。
        self.assertIsNone(report['native_last_test_norm_mixed_N_Nmm'])  # 禁止把位移范数标成力范数。
        self.assertEqual(report['native_test_norm_units'],'mixed_mm_rad')  # 原生单位必须明确。
        self.assertEqual(report['native_last_test_norm'],5e-10)  # 保留真实内部停止证据。

    def test_rigid_arm_transfers_force_and_moment(self):  # 明确检查r叉乘F及从节点方程排除。
        self.nodes.append(202)  # 增加刚臂从节点，仍保留非连续原生编号。
        self.index[202]=1  # 从节点是物理数组第二行。
        self.model['nodes'][202]=np.array([2.,0.,0.])  # 从节点位于主节点正x方向2 mm。
        self.model['elements'][7]=('FIXTURE',[101,202])  # 单个解析连接提供两节点各六分量抵抗力。
        self.model['mass'][202]=0.  # 本力传递测试不引入额外惯性。
        self.model['gravity'][202]=np.zeros(6)  # 从节点无恒载。
        self.model['fixities'][202]=[1]*6  # 从节点全部为依赖自由度，不具有独立方程。
        self.model['rigid_connections']=[{'master':101,'slave':202}]  # 声明唯一刚臂，与原生约束方向一致。
        self.applied=np.zeros((2,6))  # 为完整两节点域提供零外载。
        self.velocity=np.zeros((2,6))  # 保持静止状态以孤立约束力传递。
        self.acceleration=np.zeros((2,6))  # 保持零加速度以孤立约束力传递。
        self.internal=np.zeros((2,6))  # 初始化两端抵抗力。
        self.internal[1,1]=3.  # 从节点正y方向3 N产生主节点正z方向6 Nmm力矩。
        self.native=self.internal.copy()  # 原生未组装节点量由相同解析力构造。
        self.rhs=np.array([-6.,0.,0.,0.,-3.,0.])  # 主节点逆序方程应同时包含-6 Nmm和-3 N。
        residual,report=self.audit()  # 调用真实T转置组装和方程审计。
        self.assertEqual(residual,3.)  # 控制平动力仍为3 N，不能被从节点排除所丢弃。
        self.assertEqual(report['free_moment_max_Nmm'],6.)  # 明确保留2 mm乘3 N得到的刚臂力矩。
        self.ops.nodeDOFs.assert_called_once_with(101)  # 从节点贡献已转移，禁止重复映射其独立方程。

    def test_wrong_rhs_mapping_is_rejected(self):  # 防止方程重排被错误视为自然物理顺序。
        self.internal[0,1]=1.  # 给横向物理自由度设置1 N残差。
        self.native=self.internal.copy()  # 原生节点残差仍与独立组装匹配。
        self.rhs[1]=-1.  # 故意写入物理索引1，而正确方程号为4。
        with self.assertRaisesRegex(RuntimeError,'postcommit RHS mismatch'):  # 错误映射必须终止而非写合格证据。
            self.audit()  # 验证新增方程证据具有实际拒绝能力。

    def test_nonfinite_physical_values_are_rejected(self):  # NaN与无穷值不得通过比较运算绕过审计。
        for value in (np.nan,np.inf,-np.inf):  # 覆盖三种非有限输入。
            with self.subTest(value=value):  # 每种输入分别报告失败位置。
                self.internal[0,0]=value  # 在物理抵抗力中注入非有限数。
                with self.assertRaisesRegex(RuntimeError,'Non-finite dynamic balance'):  # 要求明确数值失败而非返回NaN。
                    self.audit()  # 实际生产审计必须拒绝该状态。

    def test_nonfinite_rhs_is_rejected(self):  # 原生节点量有限也不能掩盖方程RHS失效。
        self.rhs[0]=np.nan  # 仅污染提交后重新组装的方程右端。
        with self.assertRaisesRegex(RuntimeError,'Non-finite postcommit dynamic RHS'):  # 必须单独识别原生方程数值异常。
            self.audit()  # 原独立节点残差为零仍应终止审计。


if __name__=='__main__':  # 仅直接运行测试文件时启动标准测试驱动。
    unittest.main()  # 输出软件回归结论，不标记真实全桥诊断或训练通过。
