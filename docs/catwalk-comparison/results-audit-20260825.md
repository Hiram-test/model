# 猫道比对章 — 实验设置与结果证据审计

- 角色：Experiment Setup & Results bot
- 仓库：`Hiram-test/model`
- 工作区 / `main`：`920a94b9392811980470bc79703010748c283dfc`
- 审计日：2026-08-25
- **本章判定：`insufficient`。本研究列一律 `NA-NO-SOLVE`。禁止写通过性套话。**
- 机器表：`qoi-table.json`，检索台账：`audit-search-log.json`

本文只回答「本应跑什么」和「实际找到了什么」。没有 CalculiX 解，就没有本研究频率。

---

## 1) Skill + process mapping

只用 N00–N18 的真实 Skill 名。本章是比对（附件 2-3 表 4-1 对本研究 CalculiX），不是翻模正文，也不是 η/ε/k_c 理论对 F_att。

| 节点 | Skill 真名 | Gate | 本章角色 | 当前状态 |
|---:|---|---|---|---|
| 00 | `bridge-fem-workflow-orchestrator` | G-ORCH | 冻结 run、阻断 `BLOCKED` 下流 | 无猫道 run / `gate_ledger` |
| 10 | `bridge-cable-form-finding-initial-state` | G8B | LC-FREQ 的上游：找形 + 初应力，几何非线性 | 无 `initial_state_ir` / `form_finding_report` |
| **11** | **`bridge-load-cases-combinations-stages`** | **G9** | 冻结 LC-DEAD-PRESTRESS → **其后** LC-FREQ；人员/风另案 | 无 `load_plan.json` |
| 12 | `bridge-elements-mesh-numerical-controls` | G10 | 冻结 `*FREQUENCY` 阶数、NLGEOM、收敛计划 | 无 `numerical_controls` |
| **13** | **`bridge-pre-solve-model-verification`** | **G11** | 求解前单位/拓扑/约束/荷载预平衡 | 无 `pre_solve_verification` |
| **14** | **`bridge-solver-deck-execution`** | **G12** | 写 deck、钉 ccx 版本、干净目录、原始结果哈希 | 无 `.inp`，无 `solver_run_record` |
| **15** | **`bridge-solution-verification`** | **G13** | 残差、反力平衡、模态符号/对称、warning 处置 | 无 `.frd/.dat/.sta/.cvg` |
| **16** | **`bridge-static-response-code-review`** | **G14** | 从 verified set 提取 14 个 QoI，禁止用未验证场 | 无 `response_envelopes` |
| **17** | **`bridge-independent-check-sensitivity-credibility`** | **G15** | 表 4-1 是 ANSYS 对照，不是实测 14 阶；F_att 不是表 4-1 | 无可比的本研究根 |
| 18 | `bridge-report-audit-change-control` | G16 | 报告数字必须回链工件；本章不得发布比对通过 | **G16 = BLOCKED** |

编排顺序（应跑、未跑）：

```
N10 找形平衡（G8B）
  → N11 冻结 LC-FREQ 作用在「找形完成后的切线刚度」上（G9）
  → N12 冻结 *FREQUENCY 阶数与非线性控制（G10）
  → N13 预求解门（G11）
  → N14 写 inp + 钉 ccx + 求解（G12）
  → N15 解验证（G13）
  → N16 提取 14 QoI（G14）
  → N17 与表 4-1 对照；不与 F_att 混表（G15）
  → N18 只披露 gate 与空缺（G16）
```

N01–N09、N12 是上游契约，本章消费它们的冻结件，不在这里补几何或材料。PR #17 的 η/ε/k_c 对 F_att **不是** 表 4-1，**不是** CalculiX，**不得**填入「本研究」。`demo-rl-calculix` 与扎青 workflow **不在范围**。

---

## 2) 本应执行的实验设置（Would-be；未执行）

这是契约，不是运行记录。VM 或 CI 返回 0 不能写成科学复现。

### 2.1 工况顺序（N11）

1. **找形 / `LC-DEAD-PRESTRESS`**（N10 + N11）
   - `*STEP, NLGEOM` + `*STATIC`
   - 自重 `*DLOAD, GRAV` + 二期恒载（与密度不重复计入）
   - `*INITIAL CONDITIONS, TYPE=STRESS` 仅作种子；正式平衡由非线性静力关闭
   - 垂度控制量必须由章程冻结。附件 2-3 §2.2 写 **H = 255.56 m**；PR #18 / 理论 v1.2 用成型 **h = 227.300 m**。二者并列，**不静默折中**。未冻结则 G8B/G9 保持 `BLOCKED`，不得开 LC-FREQ。
2. **`LC-FREQ`（必须紧跟找形完成态）**
   - 线性化对象 = 找形步结束的切线刚度 + 质量
   - **禁止**把 LC-FREQ 接在 `LC-WIND-Y` 或人员步之后（PR #18 草稿 `write_inp.py` 目前就是接在风步后；该草稿即使以后写出 `.inp`，也不是本章实验）
   - `*FREQUENCY` 至少 20 阶；理论包要求验收带宽内看到前 14 个非刚体根，建议 40–60 阶以免边跨/局部根把表 4-1 的第 14 阶挤出窗
   - deck **不得**写入表 4-1 或 F_att 任何数字
3. `LC-PERSONNEL-UNIFORM` / `LC-WIND-Y` 可另作静力包络，**不是** 14 QoI 的前置刚度。

### 2.2 求解器钉扎（N14）

本章 **没有** 猫道 ccx 版本钉。本 VM 无 `ccx`。主分支扎青 workflow 安装 Ubuntu 22.04 的 `calculix-ccx`，那是另一座桥，不能冒充本钉。

正式跑必须记录并冻结：

| 项 | 要求 |
|---|---|
| 可执行文件 | `ccx` 路径 + SHA-256 |
| 版本字符串 | `ccx -v` 原文 |
| 包/镜像 | 名称、版本、OS |
| adapter / 写 deck 脚本 | 版本 + 哈希 |
| 命令行 | `ccx -i <stem>`（无交互） |
| 目录 | 干净目录 + 唯一 `SOLVE-ID` |
| 单位 | m, N, kg, s |
| 失败重试 | 只改已批准数值控制，不改材料/边界/索力/网格物理 |

### 2.3 输出请求（N14 → N15）

| 步 | 请求 | 原始文件 |
|---|---|---|
| 找形 | `*NODE FILE` → U；`*EL FILE` → S；支座反力（`RF` / `*NODE PRINT`） | `.frd` `.dat` |
| 找形收敛 | 残差、迭代、cutback | `.sta` `.cvg` + stdout/stderr |
| LC-FREQ | `*FREQUENCY`；`*NODE FILE` → U（振型） | `.dat` 特征值，`.frd` 振型 |
| 全程 | 命令行、环境、警告全文 | `solver_run_record.json` + 日志哈希 |

N15 至少：找形力/力矩全局平衡、索力保持拉力、LC-FREQ 无未解释刚体根、振型符号与对称说得通。过门后 N16 才允许填「本研究」列。配对规则（严格前 14 阶对序 vs 家族 MAC）必须由 Methodology **在看本研究根之前**冻结。

### 2.4 明确不做

- 不读 Release 中的 `cw_S10_0716t050342_a4_eq.db` 取属性
- 不把 `demo-rl-calculix` 当本桥验证
- 不把 PR #17 理论根写成 CalculiX
- 不把 F_att 或 PR #18 `isolated/TARGET-FREQ.json` 当作表 4-1
- 不把 255.56 m 与 227.300 m 折成一个数

---

## 3) 实际审计表

| ID | 搜了什么 | 在哪搜 | 找到什么 | 哈希 / 标识 |
|---|---|---|---|---|
| S01 | 猫道 `*.inp *.frd *.dat *.sta *.cvg` | 工作区 `find`；`main` `git ls-tree` 920a94b；GitHub `extension:inp catwalk` | **无** | — |
| S02 | `attachment23` PDF、`catwalk-fem`、`TARGET-FREQ` | `main` 920a94b 文件树 | **无** | — |
| S03 | 工作区 `*catwalk*` | `/workspace` | 仅 `bridge-fem-skill-suite/examples/catwalk_branch.example.yaml` | SHA-256 `ecfe62281d13e1498d6652801b4b10c8b204e6ad7c6a56c8bce32a7e44d813f9` |
| S04a | Release `catwalk-attachment23-v2.0-s10-20260716` STEP | GitHub Release | `cw_S10_0716t050342_a4_centerline.step`（77 600 240 B） | SHA-256 `d03d01e38b823df5af4c1ff9b0b175fdfb87b097b9cda9a03af5d14e9c763344` |
| S04b | 同 Release S10 `.db` | GitHub Release | `cw_S10_0716t050342_a4_eq.db`（700 186 624 B）。**未读属性。不是 CalculiX 产物。** | SHA-256 `17e0bac8717e7c32a407571d33e38dd777736b31b6656684e53449fa8c9d40fd` |
| S05 | 附件 2-3 PDF | 分支 `audit/release-inventory-20260803`；独立下载复算 | `attachment23_report.pdf` 32 页、3 188 161 B；正文为《抗风性能**研究**报告》 | SHA-256 **`d17d4061c5726c10b88cc80f3f292b16f0dbf3408e032a30840b1bcaad9173d3`**（与 inventory 原路径一致） |
| S05b | 同 PDF 的 inventory 记录 | `attachment23-pdf-matches.json` | 7 条 exact match，原路径 `01_设计资料与规范\附件2-3：猫道结构抗风性能试验报告.pdf` | 该 json SHA-256 `c358ec0241fec257bb586f3c21747c8f4cd8d059b83b04a098a7647b578cba75` |
| S05c | 纯文本摘录 | `attachment23_report_plain.txt` | 含表 4-1 十四阶 | SHA-256 `3f2a513a66d44f37a32963e4cea58feb4680d685e63f3b6f79e7e5ab05f007e0` |
| S06 | PR #18 产物 | `cursor/catwalk-inp-coord-gate-bbc1` @ `41677f35…` | 管线代码；`artifacts/.gitkeep` **空文件**；PR 正文仍写「没有真实 .inp 不写成已过门」 | empty blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`；空文件 SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| S07 | PR #18 `isolated/TARGET-FREQ.json` | 同上 | 14 个数 = F_att，**≠ 表 4-1**；文件却自称附件 2-3 频率表 | git blob `e320a5f7537a1f833edfd7327688762884c0c29d` |
| S08 | PR #17 | `cursor/eta-eps-kc-candidates-b0b4` @ `10eb1d09…` | 理论 η/ε/k_c 对 **F_att**；锁定 F_M=255.56 m；明确不是表 4-1、不是 CalculiX | 见该 PR |
| S09 | 理论 v1.2 对表 4-1 的抄录 | PR #16 / `feat/catwalk-thirteen-theory-models` @ `33662f98` | 表 4-1 十四个数与 PDF 一致；声明冻结后才打开 | 不是求解证据 |
| S10 | 本 VM `ccx` | `command -v` / `/usr` | **未安装** | — |
| S11 | `demo-rl-calculix` | 范围排除 | 不采信 | — |

**审计结论：** 参考侧只有附件 2-3 表 4-1（ANSYS 动力特性）。本研究侧没有可哈希的 CalculiX 输入或结果。G11–G16 对「本研究 14 QoI」全部 `BLOCKED`。

---

## 4) 结果表（14 QoI）

参考值只来自附件 2-3 **表 4-1**（西南交通大学，ANSYS 有限元动力特性，不是节段风洞测得的全桥 14 阶）。本研究没有特征值，故没有误差列。

| QoI | 模态 | 族（附件注） | 参考值 / Hz（表 4-1） | 本研究 | 判定 |
|---|---:|---|---:|---|---|
| QOI-01 | 1 | LS1 正对称横弯 | 0.0365 | NA-NO-SOLVE | insufficient |
| QOI-02 | 2 | VA1 反对称竖弯 | 0.0700 | NA-NO-SOLVE | insufficient |
| QOI-03 | 3 | LA1 反对称横弯 | 0.0726 | NA-NO-SOLVE | insufficient |
| QOI-04 | 4 | TA1 反对称扭转 | 0.0996 | NA-NO-SOLVE | insufficient |
| QOI-05 | 5 | VS1 正对称竖弯 | 0.1028 | NA-NO-SOLVE | insufficient |
| QOI-06 | 6 | LS2 正对称横弯 | 0.1087 | NA-NO-SOLVE | insufficient |
| QOI-07 | 7 | TS1 正对称扭转 | 0.1147 | NA-NO-SOLVE | insufficient |
| QOI-08 | 8 | 边跨模态 | 0.1149 | NA-NO-SOLVE | insufficient |
| QOI-09 | 9 | 边跨模态 | 0.1239 | NA-NO-SOLVE | insufficient |
| QOI-10 | 10 | VA2 反对称竖弯 | 0.1438 | NA-NO-SOLVE | insufficient |
| QOI-11 | 11 | LA2 反对称横弯 | 0.1449 | NA-NO-SOLVE | insufficient |
| QOI-12 | 12 | 边跨模态 | 0.1557 | NA-NO-SOLVE | insufficient |
| QOI-13 | 13 | TS2 正对称扭转 | 0.1571 | NA-NO-SOLVE | insufficient |
| QOI-14 | 14 | VS2 正对称竖弯 | 0.1744 | NA-NO-SOLVE | insufficient |

**不得填入上表「本研究」列的数：**

- F_att = {0.0296, 0.0301, 0.0601, 0.0608, 0.0714, 0.0733, 0.0735, 0.0873, 0.1012, 0.1012, 0.1098, 0.1102, 0.1155, 0.1187} Hz（PR #17；**不是表 4-1**）
- PR #18 `isolated/TARGET-FREQ.json` 的同一组数（标签与表 4-1 冲突）
- 理论 L0 抛物线根（例如 v1.2 的 0.036718559 Hz 等）：那是独立解析，不是 ccx
- 任何未带 `.dat/.frd` 哈希的口算或截图

---

## 5) 中文结果草稿（可嵌入论文；尚未求解）

### 5.1 实验设置（计划，不是已完成）

本研究拟用 CalculiX（ccx）对张靖皋南航道桥施工猫道中心线模型做「找形后频率」计算，并与附件 2-3《施工猫道结构抗风性能研究报告》**表 4-1** 的前 14 阶有限元动力特性对照。几何源仅引用 Release `catwalk-attachment23-v2.0-s10-20260716` 的中心线 STEP（SHA-256 `d03d01e3…763344`）。同 Release 的 S10 `.db` 不作为属性源。

计划工况：先做几何非线性静力找形（`LC-DEAD-PRESTRESS`），在该完成态的切线刚度上再做 `LC-FREQ`。频率步不得接在施工风或人员步之后。输出至少包括找形位移与应力、支座反力、收敛日志，以及频率步的特征值与振型。求解器版本、可执行文件哈希、命令行与原始结果哈希须在求解前钉死。目标频率不得写入输入 deck。

附件 2-3 §2.2 在基准高度公式中使用矢高 **H = 255.56 m**。未合并的建模草稿使用成型垂度 **h = 227.300 m**。两数未在章程中冻结为同一控制量，本文不将其改写成一个值。

### 5.2 结果（尚未求解）

截至 `main` `920a94b` 与本次工作区检索：仓库中不存在猫道 CalculiX 的 `.inp`、`.frd`、`.dat`、`.sta`、`.cvg`。上述 Release 只有 STEP 与 S10 `.db`。PR #18（`cursor/catwalk-inp-coord-gate-bbc1`，草稿、未合并）仅有管线代码与空的 `artifacts/.gitkeep`，没有真实 `.inp`；其 PR 正文仍写明「没有真实 .inp 不写成已过门」。本环境未安装 `ccx`。

因此，14 个对照量的「本研究」列全部为 **尚未求解（NA-NO-SOLVE）**，判定全部为 **证据不足（insufficient）**。表 4-1 的参考频率可以照录，但不能与本研究比较，也不能写成已经复现。PR #17 的理论 η/ε/k_c 对 F_att 不是表 4-1，也不是 CalculiX，不进入本表。

表 4-1 本身是报告中的 ANSYS 动力特性，不是节段模型风洞测得的全桥固有频率。在本研究求出并经验证的根之前，不存在可发布的频率比对结论。

---

## 6) 向其他 bot 要什么

### 6.1 向 Methodology bot 要（先冻结，再允许求解）

1. **14 QoI 的唯一定义**：本章只对 **表 4-1**。书面排除 F_att 与 PR #18 `TARGET-FREQ.json`。处理该 json 的错误来源标签。
2. **垂度控制量**：255.56 m（附件 2-3 风剖面/矢高）对 227.300 m（复核报告成型线）。选定一个 `sourceRef`，另一个进冲突登记，禁止折中。
3. **LC-FREQ 的上游步**：必须是找形完成态。否定「接在 LC-WIND-Y 后」的草稿。
4. **配对规则（看本研究根之前冻结）**：严格前 14 非刚体根对序，或家族 + MAC；附件无机器可读振型时如何处理边跨三阶。
5. **容差**：绝对/相对阈值；近零根规则；不得事后放宽。
6. **表 4-1 的证据等级**：ANSYS 对 ANSYS/CalculiX 是 verification，不是对风洞的 validation。
7. **隔离**：表 4-1 / F_att 对 `write_inp` 不可见。
8. **`*FREQUENCY` 阶数**与刚体根处置。
9. 人员/风是否进入本章，或只保留频率比对。
10. intended use：允许「方法演示 / 空表」，禁止「已复现附件 14 阶」。

### 6.2 向 ccx / inp 兄弟 bot 要（没有这些就继续 NA-NO-SOLVE）

1. 真实 `.inp`，路径 + SHA-256；空 `.gitkeep` 不算过门。
2. 独立 deck：找形步结束 → LC-FREQ；不要风步切线。
3. 钉死的 `ccx -v`、可执行文件哈希、OS/镜像、`SOLVE-ID`、完整命令行。
4. 原始 `.frd` `.dat` `.sta` `.cvg` + 日志的 SHA-256。
5. 从 `.dat/.frd` 抽出的特征值与振型，带单位与对象映射。
6. N13/N14/N15 工件：`pre_solve_verification`、`solver_run_record`、`raw_result_manifest`、`solution_verification_report`、`verified_result_set`。
7. 证明 deck 不含表 4-1 / F_att；证明未读 S10 `.db`。
8. 找形平衡与索力符号的 N15 记录。
9. 不要把「脚本能跑通 / VM 成功」写成 14 阶已得到。
10. 不要用 `demo-rl-calculix` 或扎青 deck 填猫道表。

---

## 7) 自评：门为什么失败，缺什么证据

### 7.1 失败原因（按强制 gate）

| Gate | Skill | 状态 | 原因 |
|---|---|---|---|
| G8B | N10 | BLOCKED | 无找形报告；垂度 255.56 / 227.300 未冻结 |
| G9 | N11 | BLOCKED | 无冻结 `load_plan`；LC-FREQ 上游步未定 |
| G11 | N13 | BLOCKED | 无 FEM-IR，无预求解统计/单位测试 |
| G12 | N14 | BLOCKED | 无 `.inp`，无 ccx 钉，无 run record |
| G13 | N15 | BLOCKED | 无原始结果，无平衡/残差 |
| G14 | N16 | BLOCKED | 无 verified result set，14 QoI 不能提取 |
| G15 | N17 | BLOCKED | 没有可与表 4-1 比的本研究根；PR #17 比的是另一组 F_att |
| G16 | N18 | BLOCKED | 报告不得把空列写成已比对 |

PR #18 自己把「没有真实 `.inp`」写成未过门。本章同意，并加严：没有哈希过的 ccx 产物，**14 行全部 insufficient**。

### 7.2 缺的证据（缺任何一项，「本研究」仍为 NA-NO-SOLVE）

1. 冻结章程：QoI = 表 4-1；垂度控制量；LC-FREQ 上游步；配对与容差。
2. 通过 G11 的模型统计与单位测试。
3. 可重放 `.inp`（SHA-256）且 LC-FREQ 在找形之后。
4. 钉死的 ccx 版本与可执行文件哈希。
5. `.frd/.dat/.sta/.cvg` + 日志哈希。
6. N15：找形平衡 + 频率步完整性。
7. 带振型依据的 14 个提取频率（不是按最近频率硬配）。
8. 独立于写 deck 的人做的对照程序。
9. 对「表 4-1 是 ANSYS、不是实测」的用途限制。

### 7.3 本章允许写什么

- 附件 2-3 表 4-1 的参考列（已用 SHA-256 `d17d4061…9173d3` 的 PDF 核对）。
- 审计：搜了什么、没找到什么。
- 计划中的实验设置。
- 一句：尚未求解，判定 insufficient。

### 7.4 本章禁止写什么

- 通过性套话、「已复现」「误差 x%」「本研究频率 = …」
- 把 F_att、TARGET-FREQ.json、L0 解析根、η/ε/k_c 填进本研究列
- 把 255.56 与 227.300 写成已经统一
- 把 STEP 或 S10 `.db` 当作已经求解
- 把 VM/CI 成功当作科学结论
- 把 `demo-rl-calculix` 或扎青 ccx 当作本桥证据

**一句话：参考表在，解不在。比对门失败。**
