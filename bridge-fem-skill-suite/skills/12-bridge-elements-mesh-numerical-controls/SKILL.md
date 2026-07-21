---
name: bridge-elements-mesh-numerical-controls
description: >
  为桥梁或猫道 FEM 中间表示选择单元族、插值阶次、积分、网格分区、局部细化、非线性算法、步长、收敛阈值和网格收敛计划。
  当几何、属性、连接、初始状态和荷载已经定义，需要生成可验证的完整 FEM-IR 时使用。
---

# 任务

你负责确定离散化和数值控制，使模型能够表达节点 06 规定的物理，并为节点 15 的解验证预先定义收敛标准。数值设置必须在求解前冻结。

# 输入契约

- analysis charter 与 control metrics；
- abstraction decisions；
- FEM geometry IR；
- material/section libraries；
- connection and boundary IR；
- initial state IR；
- load、combination、stage plan；
- solver capability matrix；
- 项目计算资源和精度目标。

每个单元选择、网格分区和数值控制项要引用 abstraction decision、sourceRef 或经批准的验证依据。

# 输出工件

- `fem_model_ir.json`；
- `element_selection_matrix.json`；
- `mesh_plan.json`；
- `convergence_plan.json`；
- `numerical_controls.json`；
- `solver_feature_requirements.json`；
- `discretization_issues.json`。

# 不可违反的规则

1. 单元类型由目标物理和响应决定，禁止因默认模板方便而选择。
2. 单元自由度、材料本构、几何非线性和连接表达必须兼容。
3. 网格尺寸由曲率、截面变化、荷载变化、连接、局部输出和误差目标共同决定。
4. 关键响应的网格收敛计划在首次正式求解前定义。
5. 梁、索和壳的局部方向必须继承节点 07 的 orientation。
6. 壳体法向、厚度偏置和层合顺序显式。
7. 低阶和高阶单元混用需定义兼容接口。
8. 缩减积分、沙漏控制、剪切锁定、膜锁定和体积锁定风险要逐项评估。
9. 非线性自动稳定、阻尼或质量缩放不得用于掩盖静力不平衡。
10. 求解器不支持的关键特性必须 `BLOCKED` 或经批准改用可验证表达。

# 工作顺序

## 1. 单元选择

按 componentGroup 和 representation 选择：

- truss/cable：仅轴向、拉力单向、初始应变；
- beam/frame：轴向、弯曲、扭转、剪切、翘曲；
- shell：膜、板弯曲、横向剪切、厚度积分；
- solid：局部三维应力、接触和复杂几何；
- spring/connector：平动、转动、间隙、摩擦和耦合；
- rigid/MPC：几何约束和荷载分配。

每个选择说明保留物理、舍弃自由度和适用范围。

## 2. 网格分区

在以下位置设置强制节点或网格边界：

- 支承、连接、集中荷载和输出点；
- 截面、材料、厚度和方向变化；
- 曲率和折线变化；
- 开孔、节点域和局部加劲；
- 接触边界；
- 施工阶段激活边界；
- 索夹、门架、横梁和索鞍连接点。

## 3. 网格质量

建立与单元族匹配的检查：

- 梁/索长度与截面尺度比；
- 曲线 chord error；
- 壳 aspect ratio、warpage、skew、Jacobian 和法向一致性；
- 实体 aspect ratio、Jacobian、负体积和过渡率；
- 弹簧零长度与局部轴；
- 刚臂长度和病态刚度风险。

阈值来自项目数值准则或求解器验证手册，并在本节点冻结。

## 4. 收敛层级

对每个关键 metric 至少定义 coarse、baseline、fine 三层，或给出经批准的等效误差估计方案。每层记录：

- 网格参数；
- 元素和自由度数量；
- 预期计算成本；
- 比较位置和结果；
- 相对/绝对差阈值；
- 单调性或振荡处理。

整体梁桥可对关键构件分段细化；壳/实体模型需关注局部峰值的路径依赖，使用截面合力或热点外推等稳定量作收敛指标。

## 5. 非线性控制

定义：

- load/displacement control；
- 增量初值、最小值、最大值；
- Newton、modified Newton、arc-length 或其他批准算法；
- 力、位移、能量残差阈值；
- 线搜索；
- 接触和摩擦迭代；
- 几何刚度和大位移；
- 允许的 cutback 序列；
- 终止条件。

数值控制变化只允许在节点 14 的批准重试序列中发生。

## 6. 输出请求

只请求能支持 charter metrics 和验证的结果：节点位移、反力、构件内力、壳合力、应力、索力、连接相对位移、能量、残差、接触状态和阶段历史。

输出位置、坐标系、截面站点和平均/外推方式明确。

## 7. 组装 FEM-IR

将 geometry、materials、sections、connections、BC、initial states、loads、combinations、stages、elements、mesh 和 outputs 合并到统一 schema。执行 ID 唯一性和引用完整性检查。

# 质量门

G10 通过条件：

1. 每个模型对象有兼容的单元族和自由度；
2. 网格边界覆盖所有结构与荷载不连续点；
3. baseline 网格满足质量阈值；
4. control metrics 有预先定义的收敛计划；
5. 非线性控制与物理问题匹配；
6. 求解器所需特性均在 capability matrix 中受支持；
7. 输出请求足以完成 G13 至 G15；
8. FEM-IR schema、ID 和引用完整；
9. 数值稳定措施不会改变目标静力物理；
10. 高风险模型的粗、基准、细网格可以自动生成。

# 失败处理

若求解器缺少某项关键单元或非线性功能，输出 feature gap。只有在节点 06 已批准等效表达、节点 17 有独立验证计划时才能继续；其余情况 G10=`BLOCKED`。

# 完成检查

1. 单元选择是否与目标物理一致？
2. 网格是否在所有结构断点和输出点分区？
3. 是否定义单元质量阈值？
4. 是否为每个关键 metric 建立收敛层级？
5. 非线性残差和步长是否在求解前冻结？
6. 是否评估锁定、沙漏和病态刚度风险？
7. 输出请求是否带位置、坐标和处理方式？
8. FEM-IR 是否通过 schema 和引用检查？
