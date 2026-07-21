---
name: bridge-report-audit-change-control
description: >
  将桥梁或猫道从资料、抽象、建模、求解、验证到规范复核的全部工件组装为可复现发布包，生成工程报告、机器清单、审计证据和变更影响图，并管理签认、替代与重跑。
  当一次分析 run 需要正式发布、归档、审查、交付，或图纸、规范、假定、脚本、求解器和用途发生变化时使用。
---

# 任务

你负责发布与配置控制。该节点确保报告中的每个关键结论能回溯到已批准输入、模型对象、求解记录和验证证据；任何变化都能定位受影响节点并触发适当重跑。发布包同时面向工程审查和机器复现。

# 输入契约

必须读取：

- analysis charter、standards manifest、approval matrix 和 scope exclusions；
- workflow run plan、gate ledger、issue register 与全部节点状态；
- 全部已发布候选工件及其 schema version、artifact ID、哈希和依赖；
- source manifest、revision register、证据图与冲突处置；
- component inventory、abstraction decisions 和完整 FEM-IR；
- solver deck manifest、run record、raw result manifest 与 verified result set；
- response envelopes、design check matrix、independent check、sensitivity 和 credibility assessment；
- 图形、表格、模型快照、日志、脚本、环境文件和审批记录；
- 当前 release request、交付格式、保密级别和保存期限。

# 输出工件

- `engineering_report.md` 或项目批准的正式文档格式；
- `engineering_report_data.json`；
- `machine_release_bundle/`；
- `release_manifest.json`；
- `artifact_dependency_graph.json`；
- `change_impact_graph.json`；
- `gate_and_issue_summary.json`；
- `approval_and_signature_record.json`；
- `reproduction_runbook.md`；
- `release_validation_report.json`；
- `supersession_register.json`。

# 发布包目录规范

```text
release/<projectId>/<releaseId>/
  00_manifest/
    release_manifest.json
    checksums.sha256
    gate_and_issue_summary.json
    approvals.json
  01_basis/
    analysis_charter.json
    standards_manifest.json
    source_manifest.json
    revision_register.json
  02_evidence/
    evidence_graph.json
    conflict_register.json
    assumption_register.json
  03_model/
    abstraction_decisions.json
    fem_model_ir.json
    solver_deck_manifest.json
    model_statistics.json
  04_runs/
    solver_run_record.json
    raw_result_manifest.json
    logs/
  05_verification/
    pre_solve_verification.json
    solution_verification_report.json
    independent_check_report.json
    sensitivity_report.json
    credibility_assessment.json
  06_review/
    response_envelopes.json
    design_check_matrix.json
    exception_register.json
  07_report/
    engineering_report.*
    figures/
    tables/
  08_reproduce/
    runbook.md
    environment-lock.*
    scripts/
  09_change_control/
    artifact_dependency_graph.json
    supersession_register.json
```

任何项目删减目录都需在 release manifest 中声明理由。

# 不可违反的规则

1. 原始来源、原始求解结果和已签认工件只读保存；发布节点不得修改上游数值。
2. 报告中的数字、表格和图形由正式机器工件生成，禁止手工重录控制值。
3. 每个结论、表格行和关键图形至少引用 responseId、checkId、claimId 或 artifactId。
4. release manifest 必须列出每个文件的相对路径、字节数、SHA-256、MIME 类型、生成工具和来源工件。
5. 报告明确 intended use、permissible use、excluded use、适用阶段、版本和限制。
6. 所有 gate 状态、边界通过条件、未关闭 issue 和批准例外必须进入报告，禁止只展示通过项。
7. 报告摘要与机器数据使用同一决策枚举和同一未舍入判定来源。
8. 图纸、规范、rule pack、脚本、环境、求解器、后处理器或假定变更都要生成新 run 或新 release；禁止覆盖旧发布包。
9. 变更影响从首个变化工件沿依赖图传播；任何手工缩小影响范围都需要工程依据和批准。
10. 节点 13、15、17、18 的 gate 在受影响重跑后强制复评。
11. 签名记录要包含签认角色、人员、范围、时间、工件哈希和签名机制。
12. 发布状态只能基于 gate ledger 自动汇总；报告措辞不能改变 gate 结论。
13. release bundle 必须在干净环境完成哈希校验和最小复现测试。
14. 包含受限或敏感资料时，按项目数据分级生成脱敏交付包，并保留内部完整包的映射。
15. 任何 superseded release 必须保留并标记替代关系、原因和生效日期。

# 工作顺序

## 1. 冻结发布候选

创建 `releaseCandidateId`，记录：

- projectId、runId、releaseId 和语义版本；
- 候选工件集合及哈希；
- 报告模板版本；
- 工具链与环境锁；
- 计划签认角色；
- 交付范围和数据分级。

冻结后新增或修改上游工件会使候选失效，必须重建候选。

## 2. 汇总 gate 与 issue

按 DAG 顺序汇总 G0–G16：

- gate 状态、评价时间、评价程序版本；
- 强制条件结果；
- caveat、bound 和 issueRefs；
- 审批状态；
- 影响的 intended use。

issue 按 severity、owner、due state、blocking、affected claims 和 closure evidence 分类。任何 blocking issue 未关闭时，release 状态为 `BLOCKED`。

## 3. 建立依赖与证据追踪

生成两张图：

- artifact dependency graph：工件级输入—输出依赖；
- claim trace graph：工程结论到 check、response、result、FEM object、abstraction、component 和 source evidence 的路径。

执行 orphan audit：

- 没有上游来源或 assumption 的模型对象；
- 没有结果依据的报告数字；
- 没有批准规则的验算；
- 没有 owner 的 blocking issue；
- 没有签认范围的关键工件。

存在关键 orphan 时禁止发布。

## 4. 生成工程报告数据层

先生成 `engineering_report_data.json`，禁止直接由聊天文本拼接最终报告。数据层至少包含：

- 项目、版本和用途；
- 采用资料与标准；
- 结构体系与模型范围；
- 抽象、单元、边界、初始状态、荷载、阶段和组合；
- 质量、网格、模型统计与求解设置；
- 求解前检查、解验证和独立复核；
- 控制响应、控制验算和利用率；
- 敏感性、不确定性和可信度；
- 假定、例外、限制和未关闭问题；
- 审批与签名。

所有 quantity 保留数值、单位、显示精度和 source reference。显示格式由模板控制，工程判定始终使用原始未舍入值。

## 5. 生成工程报告

报告建议结构：

1. 封面、版本、签认与修订记录；
2. 执行摘要与工程结论；
3. intended use、允许用途和排除用途；
4. 资料、图纸版本、标准与规则包；
5. 结构体系、施工阶段与传力路径；
6. 有限元抽象、几何、材料、截面、质量、连接和支承；
7. 初始状态、荷载、组合和施工阶段；
8. 单元、网格、求解器和数值控制；
9. 模型验证与解验证；
10. 静力响应与规范复核；
11. 独立复核、敏感性、不确定性和可信度；
12. 假定、限制、例外和未关闭问题；
13. 结论、使用条件和后续动作；
14. 附录：输入清单、模型统计、控制表、gate ledger、trace index。

执行摘要必须给出结构阶段、作用范围、控制位置、控制组合、最小裕度、关键边界和发布状态。禁止只写笼统结论。

## 6. 生成图形和表格

图形至少覆盖：

- 结构总体、坐标和构件 ID；
- 图纸—模型叠合或关键几何核验；
- 边界、释放、连接、索系和荷载示意；
- 变形、内力、索力、反力和控制位置；
- 网格收敛、敏感性和独立结果对比；
- 结论追踪与变更影响图。

每幅图带 figureId、数据工件哈希、case/stage/scenario、单位、比例、变形放大倍数和生成脚本版本。云图色标范围与裁剪规则固定并写入元数据。

表格由结构化数据生成，控制值包含完整定位和 governing case。分页、排序或显示舍入不得改变数据语义。

## 7. 组装机器发布包

复制正式工件、脚本和必要运行环境描述。保留：

- JSON/YAML/CSV 等开放机器格式；
- 求解器原生 deck 与版本信息；
- 原始结果的 manifest、哈希和存储定位；
- 后处理脚本与 rule pack；
- schema、workflow 和 Skill 版本；
- 最小可复现实例或 smoke test；
- 第三方依赖清单和许可证说明，若适用。

大型原始数据库可以采用内容寻址外部存储，release manifest 仍需记录 URI、哈希、大小、访问控制和保留策略。

## 8. 编写复现运行手册

runbook 至少说明：

- 支持的操作系统或容器；
- 依赖安装与环境锁；
- 输入工件路径和哈希校验；
- workflow 启动命令；
- solver license 与版本要求；
- 预期节点、运行状态和关键日志；
- 结果解析、gate 重算和报告生成命令；
- 最小 smoke test 的预期输出；
- 常见失败与不得采用的绕过方式。

命令中的路径、参数和版本必须可直接执行，秘密信息使用安全注入方式，禁止写入发布包。

## 9. 执行发布验证

在干净环境或受控容器中执行：

- 文件完整性与哈希校验；
- JSON Schema 和 YAML 解析；
- ID、引用与依赖完整性；
- gate 自动汇总一致性；
- 报告数值与机器工件逐项抽查；
- 图表 source reference 校验；
- 最小 smoke test 或选定控制 metric 复现；
- 安全、权限、敏感信息与恶意宏检查；
- 文件可打开性和字符编码检查。

验证报告记录环境、工具、结果、差异和批准例外。

## 10. 完成签认与发布

签认顺序遵循 approval matrix。签认人确认的范围至少包括：

- analysis lead：用途、模型和工程结论；
- checker：独立复核与关键结果；
- approver：发布范围、限制和剩余风险；
- data/configuration role：完整性、版本和复现。

签认后生成不可变 release manifest 和 checksum 文件。任何内容变化使签名失效，并进入新 release。

# 变更控制

## 1. 变更分类

每项 change request 记录类型：

- source drawing/revision；
- standard/rule pack；
- analysis purpose/acceptance；
- evidence interpretation/component inventory；
- geometry/material/section/mass；
- connection/boundary/initial state；
- load/combination/stage；
- element/mesh/numerics；
- solver/toolchain/parser；
- result extraction/check/report；
- issue closure or approval。

同时记录变更原因、发起人、时间、旧值、新值、sourceRef 和批准状态。

## 2. 影响传播

从首个 changed artifact 沿 workflow 和 claim trace graph 传播。默认规则：

- 输入文件变化：从 N02 或更早的语义节点开始；
- 规范、限值或用途变化：从 N01 开始；
- 图纸解释变化：从 N04 或 N05 开始；
- 抽象变化：从 N06 开始；
- 几何、材料、连接、初态、荷载或网格变化：从对应节点开始；
- solver 或 parser 版本变化：至少重跑受影响适配、验证和报告节点；
- 仅报告排版变化：可以只重跑 N18，但必须证明数据层未改变。

所有路径最终重评 G11、G13、G15 和 G16。若控制 claim、利用率或允许用途受影响，发布版本至少提升项目规定的相应级别。

## 3. 差异报告

每次重跑生成 machine diff 与 engineering diff：

- 工件新增、删除和哈希变化；
- 模型对象、参数、荷载和组合变化；
- 模型统计与质量变化；
- 控制响应、控制组合和利用率变化；
- gate、issue、可信度和允许用途变化；
- 报告文字与图表变化。

差异必须区分预期变化、连带变化和异常变化。异常变化未解释时不得发布。

## 4. 替代与撤回

新 release 记录 `supersedesReleaseId`。旧 release 保留状态：

- `ACTIVE`；
- `SUPERSEDED`；
- `WITHDRAWN`；
- `ARCHIVED`。

撤回需要记录原因、影响的工程决策、通知范围和替代方案。禁止删除曾用于正式决策的发布证据。

# 质量门

G16 通过条件：

1. G0–G15 的发布相关状态已自动汇总，任何 blocking issue 均已关闭；
2. 发布候选工件集合冻结，哈希和依赖完整；
3. engineering report data 与机器工件一致；
4. 报告完整说明用途、阶段、标准、模型、验证、控制结果、限制和例外；
5. 每个关键结论存在端到端 claim trace；
6. release bundle 通过 schema、引用、哈希、数值和安全校验；
7. runbook 与环境锁足以执行最小复现；
8. 变更影响图、supersession 和版本规则完整；
9. 所有签认角色按 approval matrix 完成签名；
10. release manifest 和 checksum 文件已冻结；
11. permissible use 与 G15 建议一致，未扩张分析范围；
12. release validation report 没有未批准严重项。

任何报告数值无法追踪、发布工件哈希不一致、签名缺失、blocking issue 未关闭、用途超出 G15 建议或复现校验失败时，G16=`BLOCKED`。

# 失败处理

- 报告与机器工件不一致：重建 report data 与报告，禁止手工修数字；
- 上游工件在候选冻结后变化：使候选失效，重新生成 release candidate；
- 哈希、引用或 schema 失败：返回产生该工件的节点修复，并保留失败记录；
- claim trace 断裂：补齐来源、模型映射或结果引用；无法补齐时阻断发布；
- smoke test 不可复现：冻结环境、工具版本和随机种子，追溯依赖或数值差异；
- 签认意见导致工程内容变化：创建新工件版本，重评受影响 gate；
- 仅需对外脱敏：从已签认内部包派生，记录删除/替换映射并重新做完整性校验；
- 已发布结果发现严重错误：立即标记 `WITHDRAWN`，生成影响清单并启动纠正 run。

# 完成检查

1. 发布包是否同时具备人可审查报告和机器可复现工件？
2. 报告中的每个控制数字是否由正式数据层生成？
3. 每个关键结论是否能追到 check、response、result、模型对象和源证据？
4. gate、issue、边界和限制是否完整披露？
5. 文件哈希、依赖、工具版本和环境是否冻结？
6. 是否在干净环境完成 schema、引用、哈希和 smoke test？
7. 签名是否绑定明确范围与工件哈希？
8. 变更影响是否从首个变化工件传播并重评强制 gate？
9. 新旧 release 的替代、撤回和保留状态是否明确？
10. 最终 permissible use 是否与 G15 和 analysis charter 一致？
