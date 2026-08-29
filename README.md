# Bridge FEM / Model Research Repository

本仓库同时保存桥梁有限元 Skill、张靖皋猫道、扎青吊桥、理论模型、求解输入与大型归档。它不是单一软件包，也不能把默认分支 `main` 自动理解为“最新计算模型”。

## 从这里开始

- [仓库总索引](docs/REPOSITORY_INDEX.md)：项目边界、当前入口、状态定义和 Release 登记。
- [张靖皋猫道索引](CATWALK_INDEX.md)：猫道理论、ANSYS、CalculiX、抖振和审计成果的唯一导航页。
- [分支登记表](docs/BRANCH_REGISTER.md)：现存全部分支的用途、状态、关联 PR 和后续处置。
- [命名规则](docs/NAMING_CONVENTION.md)：新分支、运行目录、输入文件、结果包和 Release 的统一命名方式。

## 当前关键入口

| 方向 | 唯一推荐入口 | 状态 | 使用边界 |
|---|---|---|---|
| 猫道 ANSYS 动力重建 | [`feat/catwalk-ansys-clean-dynamics`](https://github.com/Hiram-test/model/tree/feat/catwalk-ansys-clean-dynamics) / [PR #26](https://github.com/Hiram-test/model/pull/26) | `ACTIVE_INPUT_ONLY` | 已写输入，尚未以求解结果证明静力、模态或自由衰减通过 |
| 猫道 ANSYS 历史计算链 | [`f99-chain-closure`](https://github.com/Hiram-test/model/tree/f99-chain-closure) | `FROZEN_EVIDENCE` | 保存 S10→C20→D10→E10→E20 计算与消融，不作为新的干净动力基态 |
| 猫道 CalculiX 三维线 | [`cursor/agentic-catwalk-fea-d416`](https://github.com/Hiram-test/model/tree/cursor/agentic-catwalk-fea-d416) / [PR #23](https://github.com/Hiram-test/model/pull/23) | `ACTIVE_BLOCKED` | 仍在门禁和求解器兼容性复核中，不构成工程结论 |
| 猫道理论模型 | [`feat/catwalk-thirteen-theory-models`](https://github.com/Hiram-test/model/tree/feat/catwalk-thirteen-theory-models) / [PR #16](https://github.com/Hiram-test/model/pull/16) | `FROZEN_ARCHIVE` | 保存十三模型原文与可复现包 |
| 双 MCT 降阶抖振 | [`feat/double-mct-catwalk-buffeting`](https://github.com/Hiram-test/model/tree/feat/double-mct-catwalk-buffeting) | `BOUNDED_REFERENCE` | 可用于机制和流程对照，不替代完整三维动力模型 |
| Bridge FEM Skill Suite | [`bridge-fem-skill-suite/`](bridge-fem-skill-suite/) | `PUBLISHED_TOOLING` | N00–N18 Skill、schema 与工作流定义 |
| 扎青吊桥 | [PR #9](https://github.com/Hiram-test/model/pull/9) 及其子 PR | `SEPARATE_PROJECT` | 与张靖皋猫道分开管理，不能交叉引用模型状态 |

## 仓库使用规则

1. `main` 只承担稳定文档、公共工具和导航入口，不代表所有研究分支已经合并，也不代表最新计算结论。
2. 任何频率、位移、索力或抖振结果，都必须同时给出输入文件、求解器版本、运行目录、结果文件和提交 SHA；“求解完成”不等于“工程有效”。
3. `cursor/*`、`agent/*` 和 `work/*` 是历史自动化或临时工作分支。其内容只有被总索引登记后，才能作为可定位证据；不能仅凭分支名中的 `final`、`complete` 或 `latest` 判断有效性。
4. 新工作统一使用 [命名规则](docs/NAMING_CONVENTION.md)。既有分支不强制改名，以免破坏链接和证据谱系。
5. 分支删除、PR 关闭、文件迁移和历史压缩属于第二阶段清理，必须以登记表为依据单独执行。本次索引整理不删除任何原始成果。

## 原始输入与大型文件

- 张靖皋完整资料归档见 Release [`zhangjinggao-full-20260729`](https://github.com/Hiram-test/model/releases/tag/zhangjinggao-full-20260729)。
- S10 历史平衡 DB 与中心线 STEP 见 Release [`catwalk-attachment23-v2.0-s10-20260716`](https://github.com/Hiram-test/model/releases/tag/catwalk-attachment23-v2.0-s10-20260716)。
- 猫道 CCX 大型结果包见 Release [`catwalk-ccx-frd-20260826`](https://github.com/Hiram-test/model/releases/tag/catwalk-ccx-frd-20260826)。
- 扎青吊桥原始 DWG 子集见 [`source-inputs/zhaqing-suspension-bridge/`](source-inputs/zhaqing-suspension-bridge/)。

索引更新时间：2026-08-29。
