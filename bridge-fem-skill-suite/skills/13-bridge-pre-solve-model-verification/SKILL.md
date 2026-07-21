---
name: bridge-pre-solve-model-verification
description: >
  在桥梁或猫道有限元求解前，对 FEM-IR 执行单位、ID、拓扑、属性、自由度、约束、荷载、阶段、质量、对称性、刚体模态和简单单位测试。
  当完整模型已生成，需要在调用求解器前发现建模错误和输入遗漏时使用。
---

# 任务

你负责进行求解前模型验证。该节点使用确定性检查证明“输入文件内部一致、传力路径闭合、单位和数量级合理、约束和荷载能按预期工作”。任何 CRITICAL 错误都要在求解前阻断。

# 输入契约

- analysis charter；
- 完整 FEM model IR；
- load ledger；
- convergence plan；
- abstraction validation plan；
- geometry、property、constraint 和 load audit；
- 项目预求解阈值。

# 输出工件

- `pre_solve_verification.json`；
- `model_statistics.json`；
- `unit_and_dimension_audit.json`；
- `connectivity_and_dof_audit.json`；
- `load_mass_balance_precheck.json`；
- `unit_test_results.json`；
- `pre_solve_issues.json`。

# 不可违反的规则

1. 预求解检查独立于目标求解器 deck 生成。
2. schema 通过只代表格式正确，仍需物理检查。
3. 求解器警告不能替代本节点检查。
4. 单位、坐标和符号错误按 CRITICAL 处理。
5. 任何未引用 material、section、node、element、load 或 stage 都要登记。
6. 模型中不允许存在未解释的孤立连通分量。
7. 荷载总量和质量总量要与上游 ledger 对账。
8. 约束应允许预期刚体模态数量，且不产生额外机制。
9. 简单单位测试失败时禁止正式求解。
10. 预求解检查脚本版本和阈值必须固定。

# 工作顺序

## 1. 数据契约检查

验证：

- envelope 和 FEM-IR schema；
- ID 唯一性；
- 所有引用存在；
- 单位可解析；
- 坐标系存在且无循环；
- stage 和 combination 引用合法；
- sourceRefs/assumptionRefs 覆盖。

## 2. 数量级与单位

统计结构 extents、最小/最大构件长度、截面尺寸、材料模量、密度、弹簧刚度、荷载和初张力。与项目合理范围、图纸和 ledger 对比。

重点查找：mm/m、N/kN、kg/t、Pa/MPa、角度 deg/rad、密度/重度混淆。

## 3. 拓扑与连通

检查：

- 连通分量；
- 孤立节点和元素；
- 重复节点/元素；
- 跨越但未连接；
- 非预期刚性短路；
- load-path graph 到 FEM graph 的映射；
- 支承、锚固和基础路径。

## 4. 属性覆盖

确保每个元素有 material、section/thickness、orientation 和 stage。检查零/负面积、惯性、密度、厚度和刚度。

## 5. 约束与刚体模态

构建约束矩阵或简化刚度图，检查：

- 预期刚体自由度；
- 约束线性相关；
- 零刚度机制；
- 过刚连接环；
- 对称边界；
- 单向和接触初始状态。

可执行无荷载小扰动或低阶特征值预检查。该结果只用于发现机制，不替代正式模态分析。

## 6. 荷载与质量预平衡

对每个 LC 和 stage 计算输入层面的总力、总矩、质量和重心。与节点 11 load resultant 和节点 08 mass ledger 比较。

## 7. 单位测试

至少执行以下适用测试：

- 单跨简化自重反力；
- 关键连接单位平动/转动；
- 支座导向方向单位荷载；
- 对称结构对称荷载；
- 索单元小扰动与拉力方向；
- 壳法向压力方向；
- prescribed displacement 反力方向；
- 阶段激活前后自由度和质量变化。

测试可以使用内部小型线性求解器或符号/解析计算，不依赖正式 solver deck。

## 8. 模型统计

输出节点、元素、自由度、约束方程、材料、截面、工况、组合、阶段、质量、连通分量和高敏感情景数量，为后续运行对比建立基线。

# 质量门

G11 通过条件：

1. schema、ID、引用、单位和坐标全部合法；
2. 无 CRITICAL 拓扑断链、孤立或误连；
3. 属性覆盖 100%；
4. 约束矩阵无非预期机制和相关性；
5. 荷载、质量和重心与 ledger 一致；
6. 所有强制单位测试通过；
7. 阶段激活和状态继承完整；
8. 数量级检查无异常；
9. 模型统计与 abstraction/component inventory 对账；
10. 检查脚本与阈值已记录。

# 失败处理

任何 CRITICAL 错误回到最早负责节点修订。例如质量重复回到节点 08 或 11，支座方向错误回到节点 09，拓扑断链回到节点 07。禁止在 solver deck 生成脚本中临时补节点、约束或荷载。

# 完成检查

1. 是否检查 schema 之外的物理一致性？
2. 是否完成单位和数量级扫描？
3. 是否将 load-path graph 映射到 FEM topology？
4. 是否检查刚体模态、机制和约束相关性？
5. 质量和荷载是否与 ledger 对账？
6. 是否执行关键连接、支座、索和阶段单位测试？
7. 是否输出可比较的模型统计基线？
8. 是否把错误路由回正确上游节点？
