---
name: bridge-solution-verification
description: >
  对桥梁或猫道求解结果执行残差、反力平衡、自由体平衡、能量、收敛、网格、步长、路径、模式和异常结果检查，确认数值方程得到足够可靠的解。
  当求解器已完成运行，需要区分数值成功、离散误差和工程可用性时使用。
---

# 任务

你负责解验证。该节点回答“离散方程是否被充分求解、结果是否满足平衡、关键输出是否对网格和数值设置稳定”。它不承担规范承载力判断。

# 输入契约

- analysis charter 与 control metrics；
- FEM-IR；
- solver run record、日志和 raw result manifest；
- convergence plan；
- pre-solve verification 基线；
- 粗、基准、细网格结果；
- 多情景和多阶段结果。

每项验证检查要引用结果字段、FEM 对象、工况和 sourceRef/provenance 链，确保异常可追到输入与模型。

# 输出工件

- `solution_verification_report.json`；
- `verified_result_set.json`；
- `global_equilibrium_report.json`；
- `substructure_free_body_report.json`；
- `mesh_and_step_convergence_report.json`；
- `solver_warning_disposition.json`；
- `solution_issues.json`。

# 不可违反的规则

1. 结果解析器要记录 solver field 到 IR quantity 的映射和单位转换。
2. 全局反力平衡必须同时检查力和力矩。
3. 非线性分析检查每个增量的残差和路径，不只检查最终步。
4. 网格收敛使用预先定义的 control metrics，禁止求解后挑选较稳定指标替代失败指标。
5. 局部应力奇异点不能直接作为整体模型收敛判断。
6. solver warning 必须逐条分类和处置。
7. 对称性、符号、方向和极限情形属于强制 sanity check。
8. 多求解设置差异超过阈值时不得只选较顺眼结果。
9. 任何后处理平滑、平均和外推方式要明确。
10. 未通过 G13 的结果不得进入规范复核。

# 工作顺序

## 1. 结果完整性

检查所有请求工况、组合、阶段、情景和网格是否有结果；检查数据库是否截断、字段缺失、单位未知或对象映射失败。

## 2. 求解残差

提取每个 step/increment 的：

- force residual；
- displacement correction；
- energy residual；
- contact penetration 或约束误差；
- 迭代次数和 cutback；
- 负特征值或刚度变化。

与 numerical controls 阈值比较。

## 3. 全局平衡

对每个工况和阶段计算：

- 外荷载总力、总矩；
- 支座、锚固、基础反力总力、总矩；
- 惯性或等效作用，若适用；
- 不平衡绝对值和相对值。

同时按全局坐标和关键局部坐标检查。

## 4. 自由体平衡

在主梁、桥塔、墩、锚碇、猫道单跨、门架、索段和关键节点域切分自由体，比较边界内力、外荷载和连接力。该检查可发现全局平衡掩盖的局部误连。

## 5. 变形与符号

检查：

- 荷载方向与位移方向；
- 对称荷载的对称响应；
- 反对称工况的反对称响应；
- 支座自由方向位移；
- 索力拉力正号；
- 梁端内力和壳法向符号；
- 变形图是否沿传力路径连续。

## 6. 网格收敛

按 convergence plan 比较 coarse/baseline/fine：

- 位移、反力、构件内力、索力和稳定量；
- 截面合力或路径平均应力；
- 初始状态误差；
- 关键连接相对位移。

计算相对差、绝对差和收敛趋势。需要时使用 Richardson 外推或误差指标，方法和适用前提要说明。

## 7. 步长与算法敏感性

非线性模型至少比较一个更小步长或替代批准算法。检查路径、极值和最终状态是否稳定。若存在屈曲、松弛、接触切换或 snap-through，使用适用路径控制并报告分支。

## 8. solver warning 处置

将警告分为：

- benign with evidence；
- numerical concern；
- modeling concern；
- fatal。

每条警告绑定日志位置、影响对象、验证结果和关闭依据。禁止批量忽略。

## 9. 生成 verified result set

只有通过检查的工况、阶段、对象和字段进入 verified result set。任何受限结果带 caveat、适用范围和 issueRef。

# 质量门

G13 通过条件：

1. 结果字段完整、单位和对象映射正确；
2. 求解残差满足预设阈值；
3. 全局力和力矩平衡通过；
4. 关键自由体平衡通过；
5. 变形、符号、对称性和传力路径合理；
6. control metrics 达到网格收敛要求；
7. 非线性步长/算法敏感性可接受；
8. solver warnings 全部处置；
9. 多情景结果均完成相同验证；
10. verified result set 明确标注限制。

# 失败处理

残差或平衡失败时，先判断结果解析、荷载映射、约束、拓扑、非线性控制或单元质量的责任节点，并返回修订。禁止通过结果归一化、手工调整反力或删除异常工况获得通过。

# 完成检查

1. 是否检查所有工况、阶段、情景和网格结果完整性？
2. 是否同时校核力与力矩平衡？
3. 是否执行关键子结构自由体平衡？
4. 是否检查变形方向、符号和对称性？
5. 是否按预设 metrics 完成网格收敛？
6. 非线性路径和步长是否稳定？
7. 每条 solver warning 是否有处置？
8. verified result set 是否排除未验证字段？
