# 仓库总索引

更新时间：2026-08-29  
适用仓库：`Hiram-test/model`

## 1. 索引目的

本页是仓库级唯一入口，用于回答四个问题：

1. 这项成果属于哪个项目；
2. 当前应该进入哪个分支或 PR；
3. 它是活动输入、冻结证据、审查材料、历史试验还是原始归档；
4. 它能否被用于工程结论。

本页中的“状态”是版本管理状态，不是科学有效性或工程签认。

## 2. 项目边界

| 项目代码 | 项目 | 主要内容 | 当前入口 |
|---|---|---|---|
| `CATWALK` | 张靖皋施工猫道 | 理论模态、ANSYS/CCX、双 MCT、抖振、附件 2-3 对照 | [`CATWALK_INDEX.md`](../CATWALK_INDEX.md) |
| `ZHAQING` | 扎青吊桥 | CAD、找形、预应力和静力校准 | [PR #9](https://github.com/Hiram-test/model/pull/9) 及其子 PR |
| `SKILL` | Bridge FEM Skill Suite | N00–N18 技能、工作流、schema、门禁机制 | [`bridge-fem-skill-suite/`](../bridge-fem-skill-suite/) |
| `TBEAM` | T 梁基准试验 | VLA/网格或计算基准代码 | [`feat/tbeam-vla-benchmark-code-only`](https://github.com/Hiram-test/model/tree/feat/tbeam-vla-benchmark-code-only) |
| `AGENTIC` | 代理式预研 | 独立方法预研 | [`代理式预研`](https://github.com/Hiram-test/model/tree/%E4%BB%A3%E7%90%86%E5%BC%8F%E9%A2%84%E7%A0%94) |

不同项目之间禁止共享“当前模型”“已通过”“最终结果”等状态词。每个项目必须独立给出分支、提交和证据。

## 3. 状态词典

| 状态 | 含义 | 能否直接作为工程结论 |
|---|---|---:|
| `ACTIVE_INPUT_ONLY` | 当前正在使用的输入或代码，尚未完成数值验收 | 否 |
| `ACTIVE_BLOCKED` | 当前活动线，但至少一道硬门禁未通过 | 否 |
| `FROZEN_EVIDENCE` | 已冻结的计算或审计证据，允许追溯，不再随意改写 | 仅限其声明范围 |
| `FROZEN_ARCHIVE` | 原文件或可复现包归档，内容保持不变 | 取决于原文件性质 |
| `BOUNDED_REFERENCE` | 适合机制、流程或敏感性对照，但不具备完整模型覆盖 | 否 |
| `REVIEW_ONLY` | 分析、差异报告、候选参数或审查意见 | 否 |
| `SUPERSEDED` | 已被后续成果取代，仅保留谱系 | 否 |
| `ARCHIVE` | 原始资料或大型二进制文件保存位置 | 不是计算结论 |
| `NOT_ARMED` | 后续分析入口存在，但前置门禁尚未允许执行 | 否 |
| `PUBLISHED_TOOLING` | 公共工具、Skill、schema 或流程定义 | 不适用 |
| `SEPARATE_PROJECT` | 另一项目的成果，禁止与当前项目状态混用 | 取决于该项目索引 |

## 4. 当前工作入口

### 4.1 张靖皋猫道

当前 ANSYS 动力重建只认：

- 分支：[`feat/catwalk-ansys-clean-dynamics`](https://github.com/Hiram-test/model/tree/feat/catwalk-ansys-clean-dynamics)
- 审阅：[PR #26](https://github.com/Hiram-test/model/pull/26)
- 基线：[`f99-chain-closure`](https://github.com/Hiram-test/model/tree/f99-chain-closure)
- 状态：`ACTIVE_INPUT_ONLY`

当前 CCX 三维工作只认：

- 分支：[`cursor/agentic-catwalk-fea-d416`](https://github.com/Hiram-test/model/tree/cursor/agentic-catwalk-fea-d416)
- 审阅：[PR #23](https://github.com/Hiram-test/model/pull/23)
- 状态：`ACTIVE_BLOCKED`

理论与降阶成果分别冻结在：

- [`feat/catwalk-thirteen-theory-models`](https://github.com/Hiram-test/model/tree/feat/catwalk-thirteen-theory-models)：十三模型原文和可复现包，`FROZEN_ARCHIVE`；
- [`feat/double-mct-catwalk-buffeting`](https://github.com/Hiram-test/model/tree/feat/double-mct-catwalk-buffeting)：双 MCT 降阶模态与抖振，`BOUNDED_REFERENCE`；
- [`f99-chain-closure`](https://github.com/Hiram-test/model/tree/f99-chain-closure)：S10→C20→D10→E10→E20 ANSYS 消融链，`FROZEN_EVIDENCE`。

完整关系见 [`CATWALK_INDEX.md`](../CATWALK_INDEX.md)。

### 4.2 扎青吊桥

扎青吊桥与猫道是两个项目。其 CAD 主审阅入口为 [PR #9](https://github.com/Hiram-test/model/pull/9)，预应力研究分散在 PR #13、#14 和 #15。整理前不把这些分支合入猫道目录，也不以猫道索引替代扎青项目状态表。

### 4.3 Bridge FEM Skill Suite

Skill Suite 的稳定入口仍为：

- [`bridge-fem-skill-suite/skills/`](../bridge-fem-skill-suite/skills/)
- [`bridge-fem-skill-suite/workflow.yaml`](../bridge-fem-skill-suite/workflow.yaml)
- [`bridge-fem-skill-suite/schemas/`](../bridge-fem-skill-suite/schemas/)
- [`bridge-fem-skill-suite-v1.0.0.zip`](../bridge-fem-skill-suite-v1.0.0.zip)

## 5. Release 登记

目前发布的三个 Release 用途完全不同，不能互相替代。

| Release | 目标分支 | 主要资产 | 分类 | 使用边界 |
|---|---|---|---|---|
| [`zhangjinggao-full-20260729`](https://github.com/Hiram-test/model/releases/tag/zhangjinggao-full-20260729) | `agent/archive-zhangjinggao-20260729` | 51 个 `archive-*.tar.zst`、大型文件分片、总清单和恢复脚本 | `ARCHIVE` | 张靖皋原始资料的完整恢复入口；先读 manifest，再下载分卷 |
| [`catwalk-attachment23-v2.0-s10-20260716`](https://github.com/Hiram-test/model/releases/tag/catwalk-attachment23-v2.0-s10-20260716) | `main` | `cw_S10_0716t050342_a4_eq.db`、中心线 STEP | `FROZEN_EVIDENCE` / 历史参考 | S10 历史平衡模型与几何参考；不是新的干净动力初始状态 |
| [`catwalk-ccx-frd-20260826`](https://github.com/Hiram-test/model/releases/tag/catwalk-ccx-frd-20260826) | `feat/catwalk-ccx-20260826` | `catwalk-ccx-20260826.zip` | `BOUNDED_REFERENCE` | 974211b2 平面迁移模型的大型 CCX 文件；发布说明已限定为非科学结论 |

以后新增 Release 必须满足 [命名规则](NAMING_CONVENTION.md)，并在本表登记：项目、输入提交、求解器版本、资产 SHA-256、适用范围和禁止用途。

## 6. 分支与 PR 管理规则

- 全部分支用途见 [`BRANCH_REGISTER.md`](BRANCH_REGISTER.md)。
- `main` 是导航与稳定公共文件的集成分支，不自动代表最新模型。
- 代理自动生成的 `cursor/*`、`agent/*`、`work/*` 分支可以保留证据，但不得成为未登记的事实来源。
- 现有开放 PR 暂不批量关闭。第二阶段只关闭明确被取代、无独立证据价值且已在登记表中给出替代入口的 PR。
- 现有分支暂不批量改名，避免破坏提交、Issue、PR 和外部文档中的引用。
- 新分支必须使用 `feat/`、`fix/`、`audit/`、`docs/`、`chore/`、`archive/` 或 `exp/` 前缀。

## 7. 第二阶段清理清单

本次只建立非破坏式索引。后续清理按以下顺序执行：

1. 关闭已明确被取代的旧执行日志 PR；
2. 为仍需保留的临时代理分支补充归档说明；
3. 把 `main` 根目录散落的猫道生成器、审计脚本、CSV 和 INP 迁入 `projects/catwalk/legacy-main/`，同时保存原 SHA 和路径映射；
4. 把扎青、猫道、Skill 和 T 梁的 Actions 工作流分目录或按文件名前缀统一；
5. 删除分支前先创建冻结标签或归档 Release，并核对所有开放引用；
6. 最后才考虑压缩历史和减少分支数量。

在完成第 1–5 项之前，不直接删除任何计算分支或大型 Release。
