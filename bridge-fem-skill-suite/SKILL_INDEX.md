# Skill 索引

整套包含 1 个编排 Skill 与 18 个工程处理 Skill。每个节点都有输入契约、输出工件、质量门、失败处理和完成检查。

| 节点 | Skill | Gate | 主要输出 | 路径 |
|---:|---|---|---|---|
| 00 | `bridge-fem-workflow-orchestrator` | G-ORCH | `run_plan`, `gate_ledger`, `issue_register` | `skills/00-bridge-fem-workflow-orchestrator/SKILL.md` |
| 01 | `bridge-analysis-charter` | G0 | `analysis_charter`, `standards_manifest`, `response_metric_register` | `skills/01-bridge-analysis-charter/SKILL.md` |
| 02 | `engineering-source-ingestion` | G1 | `source_manifest`, `revision_register`, `source_quality_report` | `skills/02-engineering-source-ingestion/SKILL.md` |
| 03 | `engineering-drawing-data-extraction` | G2 | `drawing_entities`, `extracted_tables`, `view_register`, `extraction_issues` | `skills/03-engineering-drawing-data-extraction/SKILL.md` |
| 04 | `bridge-drawing-registration-reconciliation` | G3 | `evidence_graph`, `dimension_register`, `material_register`, `conflict_register` | `skills/04-bridge-drawing-registration-reconciliation/SKILL.md` |
| 05 | `bridge-structural-semantic-inventory` | G4 | `component_inventory`, `part_component_map`, `load_path_graph` | `skills/05-bridge-structural-semantic-inventory/SKILL.md` |
| 06 | `bridge-cad-fem-abstraction` | G5 | `abstraction_decisions`, `abstraction_validation_plan` | `skills/06-bridge-cad-fem-abstraction/SKILL.md` |
| 07 | `bridge-fem-topology-geometry-generation` | G6 | `fem_geometry_ir`, `topology_audit`, `geometry_overlay_report` | `skills/07-bridge-fem-topology-geometry-generation/SKILL.md` |
| 08 | `bridge-material-section-mass-properties` | G7 | `material_library`, `section_library`, `mass_ledger`, `property_audit` | `skills/08-bridge-material-section-mass-properties/SKILL.md` |
| 09 | `bridge-connections-boundaries-supports` | G8A | `connection_ir`, `boundary_ir`, `constraint_audit` | `skills/09-bridge-connections-boundaries-supports/SKILL.md` |
| 10 | `bridge-cable-form-finding-initial-state` | G8B | `initial_state_ir`, `form_finding_report`, `initial_state_scenarios` | `skills/10-bridge-cable-form-finding-initial-state/SKILL.md` |
| 11 | `bridge-load-cases-combinations-stages` | G9 | `load_plan`, `combination_plan`, `stage_plan`, `load_ledger` | `skills/11-bridge-load-cases-combinations-stages/SKILL.md` |
| 12 | `bridge-elements-mesh-numerical-controls` | G10 | `fem_model_ir`, `mesh_plan`, `convergence_plan`, `numerical_controls` | `skills/12-bridge-elements-mesh-numerical-controls/SKILL.md` |
| 13 | `bridge-pre-solve-model-verification` | G11 | `pre_solve_verification`, `model_statistics` | `skills/13-bridge-pre-solve-model-verification/SKILL.md` |
| 14 | `bridge-solver-deck-execution` | G12 | `solver_deck_manifest`, `solver_run_record`, `raw_result_manifest` | `skills/14-bridge-solver-deck-execution/SKILL.md` |
| 15 | `bridge-solution-verification` | G13 | `solution_verification_report`, `verified_result_set` | `skills/15-bridge-solution-verification/SKILL.md` |
| 16 | `bridge-static-response-code-review` | G14 | `response_envelopes`, `design_check_matrix`, `exception_register` | `skills/16-bridge-static-response-code-review/SKILL.md` |
| 17 | `bridge-independent-check-sensitivity-credibility` | G15 | `independent_check_report`, `sensitivity_report`, `credibility_assessment` | `skills/17-bridge-independent-check-sensitivity-credibility/SKILL.md` |
| 18 | `bridge-report-audit-change-control` | G16 | `engineering_report`, `machine_release_bundle`, `release_manifest`, `change_impact_graph` | `skills/18-bridge-report-audit-change-control/SKILL.md` |

## 使用原则

节点 00 只负责编排、状态和变更传播。N01–N18 依次形成不可变工件。下游不得读取未通过 schema 或 gate 的上游草稿。
