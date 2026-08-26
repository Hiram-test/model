# C10 单 TYPE72 连接候选生成结果

状态：`STATIC_PREPARE_GATE_PASSED_VALIDATION_PENDING`。本包从最终已执行 `S10_SECTION_SHEAR_20260716T050342389124Z` 直接打可逆补丁，没有运行旧物理 builder，也没有启动 MAPDL。

## 已闭合

- 原 5,078 条 CERIG：3,124 条 UXYZ、1,954 条 ALL。
- 候选：5,078 个 TYPE72 rigid beam，一条逻辑连接对应一个元素；辅助节点=0、TYPE73=0、MPC184 总数=5,078。
- 全量证明 3,124 个 UXYZ slave 只连接平移型 LINK10/LINK180，1,152 个另带 KEYOPT(3)=2 的平移 MASS21；转动型单元、力矩载荷、D、CP、CE 消费者均为零。
- 因此旧链 `master—TYPE72—aux—TYPE73—slave` 可在物理 UXYZ 空间缩并为 `master—TYPE72—slave`，同时删除会在非线性重组中失秩的中间链。
- TYPE72 采用 direct elimination 并保留几何应力刚度；不存在罚刚度参数、罚函数滑移、弱弹簧或 KEYOPT(5) 绕过。
- 十项非连接 include 与最终 S10 逐字节相同；质量、荷载、初态、D=3,968、CP=12 均未改。
- 候选 include 删除新增块并恢复 CERIG 后，SHA-256 精确回到 `72012ebbd107cf377c2178561b9008606aeb894c4f7879110d13c30d2a417330`。
- 主控反向规范化后逐字节恢复 S10；LS1/LS2、80阶 LANB、NSOL/VENG 输出均保留。
- 已生成 3 个生产拓扑平移载荷、3 个 0.1 rad 有限转动和 6 个 ALL 荷载，共 12 份微模型输入，完成数仍为 0。

## 尚未闭合

- 未执行 12 个微测试、MPC184 装配切线数值秩、全桥初始平衡静力和全桥模态。
- 数值硬门包括 solver error=0、small/zero/negative pivot=0、自动 CNVTOL 重置=0、同一案例方程数恒定。
- S10 继承的初始索力—外荷载平衡语义仍需在全桥静力中复核，不能以输入静态审计代替。
- 逐连接图纸编号仍缺失；当前只能用于连接修复验证，不能用于生产签认。
- 因此 `launch_allowed=false`、`valid_for_production=false`。

核心审计见 `qa/uxyz_slave_projection_audit.json`、`qa/model_single_difference_audit.json`、`qa/constraint_audit.json`、`qa/pre_solve_verification.json` 和 `qa/connection_mapping.csv`。
