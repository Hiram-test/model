# Bridge FEM Skill Suite

本仓库保存 Bridge FEM 19 节点 Skill Suite 的可安装源码包、桥梁原始输入资料、Skill Gate 执行复盘和仓库级执行 Hook。

## 可安装 Skill

- [`bridge-fem-skill-suite/skills/`](bridge-fem-skill-suite/skills/)：N00–N18 的 19 个 `SKILL.md`。
- [`bridge-fem-skill-suite/workflow.yaml`](bridge-fem-skill-suite/workflow.yaml)：节点依赖、条件分支和 Gate 定义。
- [`bridge-fem-skill-suite/schemas/`](bridge-fem-skill-suite/schemas/)：正式工件 schema。
- [`bridge-fem-skill-suite-v1.0.0.zip`](bridge-fem-skill-suite-v1.0.0.zip)：与展开目录内容一致的原始发布包。

## 仓库级执行 Hook

- [`.codex/hooks.json`](.codex/hooks.json)：Codex lifecycle Hook 配置。
- [`.codex/hooks/bridge_fem_hooks.py`](.codex/hooks/bridge_fem_hooks.py)：Codex 生命周期事件分发、上下文恢复和工具审计。
- [`.codex/hooks/bridge_fem_run.py`](.codex/hooks/bridge_fem_run.py)：确定性 run 初始化、节点进入、N17 计划冻结和 run 关闭。
- [`.codex/hooks/bridge_fem_policy.py`](.codex/hooks/bridge_fem_policy.py)：solver、原始结果、Gate 写入、发布和完成声明防线。
- [`.codex/hooks/bridge_fem_receipts.py`](.codex/hooks/bridge_fem_receipts.py)：逐条件 Gate receipt、工件哈希、审批和上游通行校验。
- [`.codex/hooks/node_hook_policy.json`](.codex/hooks/node_hook_policy.json)：19 个节点的规定工件、Gate 条件数量、审批和正式通行策略。
- [`docs/bridge-fem-hook-enforcement.md`](docs/bridge-fem-hook-enforcement.md)：节点覆盖、启用方式、运行状态和 Gate receipt 说明。

首次拉取或 Hook 内容变化后，需要在 Codex CLI 运行 `/hooks`，审阅并信任仓库级 Hook。Hook 未受信任时不会执行。

## 原始输入

- [`source-inputs/zhaqing-suspension-bridge/`](source-inputs/zhaqing-suspension-bridge/)：扎青吊桥建模使用的原始 DWG 子集。

## 扎青吊桥 CAD 参考模型

- [`deliverables/README.md`](deliverables/README.md)：v0.2 FreeCAD、STEP、预览、米制 IR 和验证报告的用途与限制。
- [`deliverables/Zhaqing_Suspension_Bridge_CAD_Reference_v0.2.FCStd`](deliverables/Zhaqing_Suspension_Bridge_CAD_Reference_v0.2.FCStd)：包含 N07 分析参考层以及索鞍、主锚、风锚、塔和基础的只读详图参考层。
- [`deliverables/cad_detail_preview.png`](deliverables/cad_detail_preview.png)：新增参考对象的立面、平面和三维预览。

## Skill Gate 复盘

- [`docs/skill-gate-fidelity-postmortem-2026-07-22.md`](docs/skill-gate-fidelity-postmortem-2026-07-22.md)：记录一次“Skill 已调用但 Gate 未被忠实执行”的失败。相关试算模型、求解结果和旧执行日志已经撤下，不构成任何工程证据。
- [`docs/zhaqing-model-omission-conclusion.md`](docs/zhaqing-model-omission-conclusion.md)：只保留本次模型漏项的四条根因和一条流程结论。

## 扎青吊桥状态声明

旧 CAD-001、CAD-002 模型及其自报任务包、Gate 台账和派生截图已经撤下。仓库当前发布的是 N00–N07 几何审查范围内的 CAD 参考模型；它不是制造级 CAD、完整 FEM、求解结果或工程签认成果。新增详图对象均为 `AnalysisParticipation=NONE`，其中尚未唯一配准的半径、截面和全局放置继续保留 `UNRESOLVED_PLACEMENT` 状态。
