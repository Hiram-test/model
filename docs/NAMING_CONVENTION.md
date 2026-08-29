# 仓库命名规则

生效日期：2026-08-29  
适用范围：`Hiram-test/model` 后续新增分支、目录、输入文件、运行产物、报告和 Release。

既有分支和文件不强制改名，以免破坏 PR、Issue、外部报告和哈希谱系；它们通过 [`BRANCH_REGISTER.md`](BRANCH_REGISTER.md) 解释。新内容必须执行本规则。

## 1. 基本原则

命名必须能够直接回答：项目是什么、求解器或方法是什么、分析阶段是什么、状态是什么、何时产生。

禁止只使用以下词语作为主要身份：

- `final`
- `latest`
- `complete`
- `new`
- `test`
- 随机代理后缀
- 未解释的单字母版本

这些词不能证明成果有效，也不能替代提交 SHA、运行清单和状态门禁。

## 2. 项目代码

| 项目代码 | 含义 |
|---|---|
| `catwalk` | 张靖皋施工猫道 |
| `zhaqing` | 扎青吊桥 |
| `skill` | Bridge FEM Skill Suite |
| `tbeam` | T 梁基准试验 |
| `agentic` | 代理式方法预研 |
| `repo` | 仓库级文档、索引和维护 |

分支名、目录名和 Release tag 使用小写英文项目代码。中文用于 README、报告标题和说明，不用于新分支名。

## 3. 分支命名

统一格式：

```text
<type>/<project>-<scope>[-<yyyymmdd>]
```

允许的 `<type>`：

| 前缀 | 用途 | 示例 |
|---|---|---|
| `feat/` | 新模型、输入链、功能或可交付成果 | `feat/catwalk-ansys-clean-dynamics` |
| `fix/` | 修复已定位的问题，不改变项目目标 | `fix/catwalk-ansys-mass-inertia` |
| `audit/` | 来源、质量、坐标、结果或 Release 审计 | `audit/catwalk-result-lineage-20260829` |
| `docs/` | 只改文档和报告 | `docs/catwalk-modal-methodology` |
| `chore/` | 仓库维护、索引、CI 整理 | `chore/repository-index-20260829` |
| `archive/` | 原始资料或冻结成果归档 | `archive/catwalk-source-20260729` |
| `exp/` | 参数消融、敏感性或一次性数值试验 | `exp/catwalk-ansys-connection-stiffness` |

新工作不再使用：

- `cursor/`、`agent/`、`work/` 作为长期规范分支前缀；
- 中文分支名；
- 与项目无关的代理会话 ID 作为唯一身份；
- `final` 或 `latest` 作为分支状态。

代理工具可以创建临时分支，但在保留为长期证据前，必须登记到分支表，或转入规范的 `feat/`、`audit/`、`archive/` 分支。

## 4. 项目目录

目标目录结构为：

```text
projects/
  catwalk/
    source/
    theory/
    ansys/
    ccx/
    rom/
    validation/
    reports/
  zhaqing/
    source/
    cad/
    fem/
    validation/
  tbeam/
  agentic/
tooling/
  bridge-fem-skill-suite/
docs/
  repository/
```

现有目录暂不整体搬迁。迁移时必须同时提交：

- 旧路径；
- 新路径；
- 原文件 SHA-256 或 Git blob SHA；
- 是否仅移动、是否改写；
- 所有受影响的 README 和外部链接。

## 5. 求解输入文件

同一计算包内使用两位数字表示执行阶段：

```text
00_<assemble-or-common>.inp
10_<static-equilibrium>.inp
20_<prestressed-modal>.inp
30_<zero-load-transient>.inp
40_<free-decay-or-identified-test>.inp
50_<forced-response>.inp
60_<buffeting>.inp
90_<postprocess-or-audit>.inp
```

例如当前 ANSYS 干净动力包：

- `00_assemble_physical_model.inp`
- `10_static_equilibrium.inp`
- `20_prestressed_modal.inp`
- `30_zero_load_transient.inp`
- `40_ta1_twist_release.inp`
- `50_buffeting_not_armed.inp`

规则：

1. `00_*` 只装配模型，不执行求解；
2. 静力、模态、瞬态和抖振不得混在一个含糊的 `main.inp` 中；
3. 物理输入、数值稳定变体和试验性参数必须分文件；
4. 未经允许执行的入口在文件名中写明 `not_armed`；
5. 每个入口有唯一 jobname，禁止不同分析共用结果文件名。

## 6. 运行目录

统一格式：

```text
<PROJECT>-<SOLVER>-<STAGE>-<RUNID>-<UTC_TIMESTAMP>
```

建议字段：

- `<PROJECT>`：`CATWALK`、`ZHAQING`、`TBEAM`；
- `<SOLVER>`：`ANSYS`、`CCX`、`PYROM`、`THEORY`；
- `<STAGE>`：`EQ`、`MOD`、`TRN0`、`DECAY`、`BUF`、`AUDIT`、`EXP`；
- `<RUNID>`：连续编号，如 `A01`、`C03`；
- `<UTC_TIMESTAMP>`：`YYYYMMDDTHHMMSSZ`。

示例：

```text
CATWALK-ANSYS-EQ-A01-20260829T123000Z
CATWALK-ANSYS-DECAY-A03-20260830T041500Z
CATWALK-CCX-MOD-C02-20260831T093000Z
```

旧的 `S10`、`C20`、`D10`、`E10`、`E20` 保留为历史试验编号，但不再跨项目或跨求解器复用。

## 7. 结果文件与清单

每个运行目录至少包含：

```text
RUN_MANIFEST.md
INPUT_SHA256SUMS.txt
STATUS.txt
solver/
results/
qa/
report/
```

`RUN_MANIFEST.md` 至少记录：

- 项目代码；
- 分支和提交 SHA；
- 输入主文件及 SHA-256；
- 求解器名称、版本和启动命令；
- 单位和坐标系；
- 上游平衡态或父运行；
- 分析阶段；
- 硬门禁及结果；
- 允许形成的结论；
- 禁止用途。

`STATUS.txt` 只允许使用预定义状态，例如：

```text
INPUT_PREPARED
RUNNING
FAILED_NUMERICAL
FAILED_GATE
PASSED_GATE
FROZEN_EVIDENCE
NOT_ARMED
```

不得使用不具备判定条件的 `SUCCESS`、`FINAL` 或 `VALIDATED`。

## 8. 报告命名

统一格式：

```text
<project>_<topic>_<document-type>_<yyyymmdd>.<ext>
```

示例：

```text
catwalk_ta1_free_decay_methodology_20260829.pdf
catwalk_ansys_static_gate_report_20260830.md
catwalk_ccx_modal_comparison_20260831.csv
```

同一报告的 `.tex`、`.pdf`、图片和数据放入同一报告目录。版本演进依靠 Git 提交和 tag，不在文件名中无限追加 `v2_final_new2`。

确需对外发布版本时使用语义版本：

```text
catwalk_ansys_clean_dynamics_v1.0.0.pdf
```

## 9. Release 命名

统一 tag 格式：

```text
<project>-<artifact>-v<major.minor.patch>-<yyyymmdd>
```

示例：

```text
catwalk-ansys-clean-dynamics-v1.0.0-20260830
catwalk-source-archive-v1.0.0-20260729
catwalk-ccx-true3d-results-v0.3.0-20260831
```

Release 名称必须写明其性质：

- `Source archive`
- `Input package`
- `Solver results`
- `Frozen evidence`
- `Review-only report`

Release 正文必须列出目标提交、全部资产大小和 SHA-256、恢复方法、适用范围及禁止用途。大型二进制文件不得仅凭文件名判断与哪次输入对应。

## 10. PR 标题

建议格式：

```text
[STATUS][PROJECT][METHOD] 简明任务名称
```

允许的首段状态：

- `[ACTIVE]`
- `[REVIEW]`
- `[FROZEN]`
- `[ARCHIVE]`
- `[SUPERSEDED]`
- `[BLOCKED]`

示例：

```text
[ACTIVE][CATWALK][ANSYS] 干净动力输入包
[REVIEW][CATWALK][THEORY] TA1 可达域分析
[ARCHIVE][CATWALK][SOURCE] 张靖皋完整资料归档
```

PR 正文必须明确 base、head、输入来源、是否执行求解、是否允许形成结论、被哪个入口取代或将取代谁。

## 11. 有效性声明

文件名、分支名、PR 状态和 Release 状态都不是工程验证。任何正式结果必须形成以下闭环：

```text
source → input → solver run → raw result → QA gate → interpretation → report
```

每一箭头都要能够通过路径和哈希追溯。缺少任一环节时，只能使用 `REVIEW_ONLY`、`ACTIVE_BLOCKED` 或 `BOUNDED_REFERENCE` 等受限状态。
