# Bridge FEM Skill Suite

本仓库保存 Bridge FEM 19 节点 Skill Suite 的可安装源码包、桥梁原始输入资料和经审计的独立工作日志。

## 可安装 Skill

- [`bridge-fem-skill-suite/skills/`](bridge-fem-skill-suite/skills/)：N00–N18 的 19 个 `SKILL.md`。
- [`bridge-fem-skill-suite/workflow.yaml`](bridge-fem-skill-suite/workflow.yaml)：节点依赖、条件分支和 Gate 定义。
- [`bridge-fem-skill-suite/schemas/`](bridge-fem-skill-suite/schemas/)：正式工件 schema。
- [`bridge-fem-skill-suite-v1.0.0.zip`](bridge-fem-skill-suite-v1.0.0.zip)：与展开目录内容一致的原始发布包。

## 原始输入

- [`source-inputs/zhaqing-suspension-bridge/`](source-inputs/zhaqing-suspension-bridge/)：扎青吊桥建模使用的原始 DWG 子集。

## 其他独立工作日志

- [`NEXT_STEPS.md`](NEXT_STEPS.md)：张靖皋猫道 Pro 模型的后续执行入口与优先级。
- [`docs/zhangjinggao-catwalk-automation-execution-log-2026-07-22.md`](docs/zhangjinggao-catwalk-automation-execution-log-2026-07-22.md)：张靖皋猫道图纸自动化、十九 Skill 与 ANSYS 三维静力执行日志。

上述猫道日志属于另一条已审计工作链，不构成扎青吊桥 CAD 的 Gate 证据。

## 扎青吊桥状态声明

旧 CAD-001、CAD-002 模型及其自报任务包、Gate 台账和派生截图已经撤下。仓库当前不发布任何扎青吊桥 CAD 或 FEM 成果；新的模型必须由已安装 Skill 在全新 run 中按原生契约生成，并由独立 Gate 校验器判定。
