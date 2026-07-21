# Schema 目录

本目录包含通用 envelope 与关键节点的业务结构约束。所有正式工件先通过通用 envelope，再通过对应业务 schema。schema 版本与 Skill 版本独立管理；不兼容变化提升 major version。

## 覆盖关系

| 节点 | 主要 schema |
|---|---|
| 00 | `gate_ledger.schema.json` |
| 01 | `analysis_charter.schema.json` |
| 02 | `source_manifest.schema.json` |
| 03 | `drawing_entities.schema.json` |
| 04 | `evidence_graph.schema.json` |
| 05 | `component_inventory.schema.json` |
| 06 | `abstraction_decisions.schema.json` |
| 07 | `fem_geometry_ir.schema.json` |
| 08 | `property_bundle.schema.json` |
| 09 | `connection_boundary_ir.schema.json` |
| 10 | `initial_state_ir.schema.json` |
| 11 | `load_plan.schema.json`、`stage_plan.schema.json` |
| 12 | `fem_ir.schema.json` |
| 13 | `pre_solve_verification.schema.json` |
| 14 | `solver_run_record.schema.json` |
| 15 | `solution_verification.schema.json` |
| 16 | `response_envelopes.schema.json`、`design_check_matrix.schema.json` |
| 17 | `credibility_assessment.schema.json` |
| 18 | `release_manifest.schema.json` |

## 校验顺序

1. JSON/YAML 语法；
2. envelope 字段；
3. 业务 schema；
4. 跨工件引用完整性；
5. ID 唯一性与类型前缀；
6. quantity 单位与坐标；
7. gate 业务规则。

JSON Schema 负责结构完整性，工程公式、数值阈值、跨对象关系和质量门由确定性 validator 执行。
