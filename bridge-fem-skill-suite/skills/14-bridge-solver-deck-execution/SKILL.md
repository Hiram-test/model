---
name: bridge-solver-deck-execution
description: >
  将求解器无关的桥梁或猫道 FEM-IR 映射为指定软件输入文件，执行静力或阶段分析，固定软件版本、单位、特性映射、命令行、日志、重试和原始结果哈希。
  当 G11 已通过，需要调用 Abaqus、ANSYS、MIDAS、SAP2000、OpenSees、SOFiSTiK 或其他批准求解器时使用。
---

# 任务

你负责求解器适配和可重放运行。该节点不重新解释图纸，不修改工程物理，只把已批准 FEM-IR 映射为 solver deck，并记录所有映射、警告、运行参数和原始结果。

# 输入契约

- analysis charter；
- G11=PASS/PASS_WITH_BOUNDS 的 FEM-IR；
- solver target、版本和许可证环境；
- adapter version 与 feature mapping matrix；
- numerical controls 和批准重试序列；
- 资源限制、并行设置和输出请求；
- clean run directory policy。

每个 solver entity 与结果字段映射要保留 FEM-IR 对象、sourceRef 链和适配器版本，支持双向审计。

# 输出工件

- `solver_deck_manifest.json`；
- solver input files；
- `feature_mapping_report.json`；
- `solver_run_record.json`；
- stdout、stderr、message、warning 和 convergence logs；
- `raw_result_manifest.json`；
- `deck_round_trip_report.json`；
- `solver_execution_issues.json`。

# 不可违反的规则

1. 只读取冻结 FEM-IR 和任务包列出的依赖。
2. 求解器、adapter、插件、材料库和操作系统版本全部记录。
3. 内部单位到求解器单位的转换只有一个入口，并生成审计表。
4. 每个 FEM-IR 特性必须映射为 supported、approved_equivalent 或 unsupported。
5. unsupported 关键特性不得静默删除或改写。
6. deck 生成脚本不能添加未在 FEM-IR 中存在的物理对象。
7. 求解设置变化必须属于预批准 retry sequence。
8. 每次运行使用干净目录和唯一 SOLVE-ID。
9. 原始结果文件只读保存并计算哈希。
10. “程序返回 0”只表示运行完成，不代表解通过验证。

# 工作顺序

## 1. 能力匹配

将 FEM-IR 中的 element、material、connection、contact、initial state、stage、load、output 和 nonlinear control 与 solver capability matrix 逐项匹配。

输出映射表：

- IR object/feature；
- solver keyword/API；
- 参数和单位转换；
- 语义差异；
- 验证测试；
- 支持状态。

任何关键 unsupported 项立即 `BLOCKED`。

## 2. 生成 deck

使用确定性模板或 API 创建：

- 节点、元素、材料、截面；
- orientation、offset、MPC、spring、contact、BC；
- initial stress/strain、prestress、form-found geometry；
- load cases、combinations 或 stage steps；
- solver controls；
- output requests。

对象名包含稳定 ID，便于结果回映射。

## 3. deck 静态检查

在运行前解析生成 deck，检查对象数量、坐标范围、属性、荷载总量、约束、阶段和输出请求与 FEM-IR 一致。生成 round-trip diff。

允许差异只包括求解器语法、内部排序和批准的等效展开。

## 4. 执行环境

记录：

- 主机/容器镜像；
- CPU、内存、线程；
- 求解器可执行文件哈希；
- 许可证配置摘要；
- 环境变量；
- 命令行；
- 开始/结束时间；
- 随机种子，若适用。

## 5. 正式运行

执行 baseline。实时捕获收敛、奇异、负特征值、接触、单元畸变、零主元、刚度比和能量警告。

## 6. 批准重试

若运行失败，按 numerical controls 中的顺序尝试，例如减小步长、启用批准线搜索、提高迭代上限。每次重试：

- 生成新 SOLVE-ID；
- 保存变更字段；
- 保留失败结果；
- 禁止改材料、截面、荷载、边界、初始状态和物理单元。

达到最大次数后 G12=`BLOCKED`。

## 7. 原始结果登记

登记数据库、二进制结果、文本输出、重启动文件、日志和后处理索引。计算 sha256，保存求解器单位、坐标约定和结果字段说明。

# 质量门

G12 通过条件：

1. 所有关键 FEM-IR 特性有合法映射；
2. deck round-trip 与 FEM-IR 一致；
3. 求解器和 adapter 版本固定；
4. 单位转换审计通过；
5. baseline 或批准重试成功完成；
6. 没有未处理的 fatal/critical solver warning；
7. 原始结果和日志完整且有哈希；
8. 运行环境可重建；
9. 多情景、多网格和多阶段均有独立 run record；
10. 未发生物理输入的隐式修改。

# 失败处理

若 deck round-trip 发现对象数量、荷载或边界不一致，修复 adapter 并重新生成，不能手工编辑 deck 后继续。若 solver warning 指向模型机制、错误接触或负刚度，返回 G11 或更早节点处理。

# 完成检查

1. 是否逐项核对 solver feature support？
2. 单位转换是否集中且可审计？
3. deck 是否通过回读对比？
4. 每次运行是否有唯一 ID 和干净目录？
5. 是否保存完整命令、环境和日志？
6. 重试是否只改变批准数值设置？
7. 原始结果是否只读并带哈希？
8. 是否避免把运行成功等同于工程通过？
