# 桥梁与猫道 CAD→FEM→静力复核 Skill Suite

这套 Skill Suite 把“上传图纸到静力计算复核”拆成 19 个可编排节点。每个节点具有固定输入、固定输出、质量门、失败处理和下游契约。核心目标是让自动化覆盖资料接入、证据提取、工程语义化、模型生成、求解、验证、复核和报告，同时保留工程签认所需的完整证据链。

## 总体架构

系统分为三条并行链路。

**数据链路**负责把原始图纸逐步转换为可计算对象：

`原始文件 → source_manifest → drawing_entities → evidence_graph → component_inventory → abstraction_decisions → FEM-IR → solver deck → raw results → reviewed results`

**控制链路**负责执行 DAG、评估质量门、管理重试和变更影响：

`workflow.yaml → node task → schema validation → gate ledger → issue register → release manifest`

**保证链路**负责判断结果是否足以支撑项目决策：

`来源完整性 → 物理模型校核 → 数值解校核 → 独立复核 → 敏感性与可信度 → 工程签认`

## 关键原则

1. 原始文件只读保存，所有中间工件带哈希、版本和来源定位。
2. 工程语义判断由 Skill 执行，几何计算、单位换算、截面属性、荷载汇总、求解和数值检查由确定性程序执行。
3. 所有数值必须带单位、坐标系和依据；禁止跨节点传递裸数值。
4. 每个接受值都能回溯到 CAD 句柄、PDF 页码与区域、表格单元格、设计说明或经批准假定。
5. 高敏感缺失信息转化为边界情景；若情景包络无法满足验收标准，流程进入 `BLOCKED`。
6. 任何求解器不支持的特性必须显式登记；禁止静默降级为另一种物理表达。
7. 求解完成只代表程序正常结束，结果还需通过平衡、残差、网格、独立模型和规范复核。
8. 最终发布包包含允许用途、限制条件、假定、未关闭问题和签认记录。

## 节点目录

| 节点 | Skill | 主要产物 | 质量门 |
|---|---|---|---|
| 00 | workflow orchestrator | run plan、gate ledger | G-ORCH |
| 01 | analysis charter | analysis charter、standards manifest | G0 |
| 02 | source ingestion | source manifest、revision register | G1 |
| 03 | drawing extraction | drawing entities、table extraction | G2 |
| 04 | registration & reconciliation | evidence graph、conflict register | G3 |
| 05 | semantic inventory | component inventory、load-path graph | G4 |
| 06 | FEM abstraction | abstraction decisions | G5 |
| 07 | topology & geometry | geometry IR、topology audit | G6 |
| 08 | materials/sections/mass | property libraries、mass ledger | G7 |
| 09 | connections/boundaries | connection and BC IR | G8A |
| 10 | form finding/initial state | initial state scenarios | G8B |
| 11 | loads/combinations/stages | load plan、stage plan | G9 |
| 12 | elements/mesh/numerics | mesh plan、numerical controls | G10 |
| 13 | pre-solve verification | pre-solve verification report | G11 |
| 14 | solver adapter & run | solver deck、run record | G12 |
| 15 | solution verification | solution verification report | G13 |
| 16 | static response/code review | response envelopes、check matrix | G14 |
| 17 | independent check & credibility | independent check、sensitivity | G15 |
| 18 | report/audit/change control | release bundle、change graph | G16 |

## 推荐运行方式

先复制 `examples/project_manifest.example.yaml` 和 `examples/analysis_charter.example.yaml`，填入项目实际信息。随后由节点 00 读取 `workflow.yaml`，逐节点生成任务包。节点产物必须符合 `schemas/` 下的数据契约。任何质量门进入 `BLOCKED` 时，下游任务停止；修订资料或工程假定后创建新的 run，不覆盖旧记录。

## 猫道分支

猫道、主缆、斜拉索、临时索系和预应力体系触发节点 10。该节点负责线形目标、初张力、初应变、施工温度、鞍座或锚固边界、张拉顺序和几何非线性平衡。节点 11 随后施加人员、设备、面网、踏板、风荷载和施工阶段作用。示例见 `examples/catwalk_branch.example.yaml`。

## 自动化范围

可以全自动执行的工作包括文件清单、哈希、实体提取、坐标转换、数据契约校验、模型脚本生成、求解器调用、结果解析、平衡检查、网格对比、报告组装和变更影响分析。

需要工程签认的节点包括分析章程、关键冲突处理、有限元抽象、高敏感假定边界、荷载与组合规则、最终允许用途。签认记录作为下游输入的一部分，不在聊天文本中隐式完成。

## 文件说明

- `workflow.yaml`、`WORKFLOW_DIAGRAM.md`：端到端 DAG、条件分支与可视化。
- `SKILL_INDEX.md`、`ALL_SKILLS.md`、`skill_catalog.json`：节点索引、合并审阅版与机器目录。
- `common/`：统一 ID、单位、假定、状态与数据封装规则。
- `schemas/`：25 个核心工件 JSON Schema。
- `skills/`：19 个节点的独立 `SKILL.md`。
- `IMPLEMENTATION_BLUEPRINT.md`、`CONTROL_MATRIX.md`：生产自动化架构与节点控制。
- `FIRST_PROJECT_RUNBOOK.md`：首个真实项目的落地步骤。
- `examples/`：桥梁和猫道分支示例。
- `tests/`：静态 lint、黄金样例、错误注入与基准矩阵。
- `MIGRATION_FROM_CURRENT_SKILL.md`：对原有 Skill 的评审与迁移方案。
