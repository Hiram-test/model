# I08 GitHub 精确 43 工况：CCX、知识图谱与智能体推演结果摘要

## 1. 工作流输入与计算边界

- 工作流输入：`Hiram-test/model`，分支 `cursor/agentic-catwalk-fea-d416`，提交 `c1dfa02e12d82b20a1d34c389c501ce782befb49`。
- GitHub 源文件：`catwalk-fem/true3d-extreme/artifacts/extreme_weather_library.json`，blob SHA-1 `9b708839baf8e6ccf76df292556c4d5387bf9da4`。
- 43 案顺序与数量严格采用冻结源库；35 案为 `stationary_ok`，8 案为 `reference_only`。
- 每案为一个 600 s、`dt=0.05 s` 的 common-random-number 实现。结果是统一桥址映射下的描述性线性 ROM 数值筛查，不是多种子收敛、概率包络、设计包络、重现期组合或历史事件现场重现。
- 模型为 CalculiX 执行的 source-basis 150 模态坐标线性预应力切线 ROM；不包含元素级大位移更新、索松弛后的重分布、接触或局部构造非线性。

## 2. 求解与独立 QA

- 43/43 个新 I08 CalculiX 作业完成，返回码均为 0。
- 原子执行稳定性终验：43/43，通过两轮间隔复核；`I08_ATOMIC_STABILITY_AUDIT.json` SHA-256 `528f2d0a7c844905054e39772ff167a3d0145547308bec3896a8c8ffbf55bb9e`。
- 最终独立 QA：43/43 单案 `PASS`，所有逐案 checks 为 true；后处理器没有调用求解器。
- 最终 acceptance SHA-256：`fecb6b42b53d734ed6e6243f83b0edc28549aae8c74a18d2b7c9735289dc3381`。
- QA SHA 账本：493/493 通过；账本 SHA-256 `c15870383e995985afab9b54bc96bf4099db616f1ae3666b0c3ec89e964fa82e`。
- 最坏相对 Frobenius 误差：`q=1.969241e-7`、`v=1.941563e-7`，均低于 `1e-6` 门槛；最紧绝对误差门为速度端点，占限值 97.4522%，仍通过。
- 独立精确 FOH 卡闭合最坏相对误差：`q=2.481299e-13`、`v=8.185105e-14`，低于 `1e-12` 门槛。

数值 QA `PASS` 仅表示输入、求解器输出、精确 FOH 参考和恢复链闭合，不表示结构安全、施工放行或预警阈值已签署。

## 3. 响应特征值（`|mean ± 3.5σ|`）

### 3.1 35 个 `stationary_ok` 映射案

| 响应 | 最大特征值 | 工况与位置 |
|---|---:|---|
| 横向共同位移 | 1203.454183 m | `patricia_2015_peak`，L/2，正向 |
| 竖向共同位移 | 47.345424 m | `patricia_2015_peak`，3L/4，负向 |
| 左幅局部滚转 | 78.944403° | `patricia_2015_peak`，L/4，正向 |
| 右幅局部滚转 | 79.219278° | `patricia_2015_peak`，L/4，正向 |
| 系统滚转 | 34.738462° | `mt_washington_1934`，3L/4，正向 |

### 3.2 8 个 `reference_only` 平稳代理案

| 响应 | 最大特征值 | 工况与位置 |
|---|---:|---|
| 横向共同位移 | 2892.846578 m | `bridge_creek_1999_ref`，L/2，正向 |
| 竖向共同位移 | 125.484321 m | `bridge_creek_1999_ref`，3L/4，负向 |
| 左幅局部滚转 | 174.611825° | `bridge_creek_1999_ref`，L/4，正向 |
| 右幅局部滚转 | 175.351042° | `bridge_creek_1999_ref`，L/4，正向 |
| 系统滚转 | 80.173211° | `bridge_creek_1999_ref`，3L/4，正向 |

这些大位移与大转角不是非线性最终预测；它们表明线性切线 ROM 已明显超出物理适用范围，只能用于触发非线性专项复核。`reference_only` 数值不能并入真实非平稳事件的控制工况结论。

## 4. 索力与线性边界筛查

- 12 个工况、1275 个索行触发 `mean-3.5σ <= 0` 的线性统计松弛筛查；其中承重索 633 行、门架索 642 行。
- 12 案为：`goni_2020_landfall`、`tip_1979_peak`、`mangkhut_2018_peak`、`patricia_2015_peak`、`dorian_2019_landfall`、`gustav_2008_cuba_gust`、`ef4_anchor`、`ef5_anchor`、`funing_2016_ef4`、`bridge_creek_1999_ref`、`thule_1972_gust`、`mt_washington_1934`。
- `stationary_ok` 承重索最大 `mean+3.5σ=1156.009883 kN`；与来源记录的 2380 kN 单根物理索断力相比，筛查比为 `1156.009883/2380=0.485718`。
- 全 43 案承重索最大 `mean+3.5σ=1946.477414 kN`，来自 `bridge_creek_1999_ref`；该案为 `reference_only` 且触发松弛筛查，不能作为规范容量结论。
- 门架索最大 `mean+3.5σ=1843.523750 kN`；门架索断力基准缺失，状态始终为 `NOT_EVALUATED_GANTRY_BREAK_FORCE_UNAVAILABLE`。

2380 kN 比较只是“相对来源记录断力的筛查”，不构成规范容量验算结论。未触发松弛筛查也不等于物理上“未松弛”。

## 5. 知识图谱与四智能体推演

- 最终知识图谱：2520 个节点、2953 条边。
- 43 个案例均生成 4 步确定性轨迹：`AuthorityAgent -> SolverEvidenceAgent -> PhysicsBoundaryAgent -> WarningPolicyAgent`，共 172 个 AgentDecision。
- PhysicsBoundaryAgent 终态：
  - `STOP_AND_NONLINEAR_REVIEW`：12 案；
  - `REFERENCE_ONLY_NONSTATIONARY`：4 案；
  - `NUMERICAL_EVIDENCE_READY_HUMAN_REVIEW`：27 案；
  - `WAITING_FOR_SOLVER_EVIDENCE`：0 案。
- 8 个 `reference_only` 案中有 4 个同时触发松弛筛查，因此按“边界触发优先”进入 `STOP_AND_NONLINEAR_REVIEW`；其余 4 个进入 `REFERENCE_ONLY_NONSTATIONARY`。
- WarningPolicyAgent：43 案全部 `NOT_ARMED`，`dispatch=false`；没有生成蓝、黄、橙、红等未经签署的运行等级。
- 图谱 JSON SHA-256：`a0acad79cea7b2a5f4ce6256420569348808df936e800a96e793b10e9db1ffbc`。
- 43 案 trace CSV SHA-256：`a12d51d542a49675b9a4bd73f5662a9a5d0592e5dca12a1bfebbb572c3412ab4`。
- KG SHA 账本 SHA-256：`1e55edb988115abd0273fb2a0c502baf9aae8d716b825cdcfd4a6ee14a74a9c9`。

## 6. 异常处理与可追溯性

- 首轮全批 QA 曾因 scratch 双向同步回写导致 5 个 `.dat` 哈希漂移，正确地发布 `FAIL_CASE_GATES`，没有被下游 PDF/KG 消费。
- 根因法证、隔离目录、错误栈与处置记录均保存在 `I08_ERROR_LOG.md`；修复后 CCX 在 `/tmp` 完成、校验、`fsync`，再原子发布到工况目录。
- 最终 QA、KG 和 PDF 均采用排除同步的临时区、原子替换以及发布后间隔稳定性复核。

## 7. 第二章交付件

- 最终 PDF：`超长猫道智能预警系统_第二章抖振知识图谱与智能体推演_20260830_FINAL_R1.pdf`，30 页 A4。
- PDF SHA-256：`2d17882bfce050f66d68579ea42cbbf3354f69e005ce7c4e591d055f54d86c28`。
- 非第二章范围按原稿保留：第一章正文保留，第三至六章保持原有标题页；封面、目录、页眉与页码仅按第二章证据化修订同步更新。
- PDF 已通过三遍 XeLaTeX、字体嵌入/ToUnicode、全 30 页 Poppler 渲染、关键页目视检查及发布后双轮 SHA/页数/渲染稳定性复核。
