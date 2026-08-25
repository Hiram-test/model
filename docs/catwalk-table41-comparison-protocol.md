# 猫道比对章方法协议：CalculiX QoI ↔ 附件2-3 表4-1

状态：`insufficient`（2026-08-25）。This study 频率全部为空。禁止写「符合」。

适用对象：张靖皋施工猫道；对照源仅限《附件2-3 猫道结构抗风性能试验报告》表4-1 十四项。  
坐标系：`CS-CATWALK-CHAINAGE`，\(x=\)桩号\(-K16+876.000\)（米，北→南为正）。  
机器台账：[`docs/qoi/table41-qoi-register.json`](qoi/table41-qoi-register.json)。

---

## 1. Skill + 过程标签映射

只使用 `bridge-fem-skill-suite` 实名（N00–N18）。可选未合并名 `catwalk-step-inp-pipeline` 仅存在于 PR #18 分支 `cursor/catwalk-inp-coord-gate-bbc1`，不在 `main`，且 `catwalk-fem/artifacts/` 只有 `.gitkeep`，没有真实 `.inp`。六个共享名在账本中没有 `SKILL.md`，只作过程标签，不得写成已安装 Skill。

### 1.1 账本内实名（有 `SKILL.md`）

| 节点 | 实名 | Gate | 本比对章用法 |
|---:|---|---|---|
| N00 | `bridge-fem-workflow-orchestrator` | G-ORCH | 冻结 runId、任务包、哈希链；阻断任何 `BLOCKED` 工件进入提取。 |
| N01 | `bridge-analysis-charter` | G0 | 冻结 intended use =「成型态切线刚度上的固有频率家族对照」；验收写成「无章程容差则只报 delta」。 |
| N02 | `engineering-source-ingestion` | G1 | 登记附件2-3 PDF、表4-1 页定位、STEP Release；隔离非表4-1 频率表。 |
| N03 | `engineering-drawing-data-extraction` | G2 | 从表4-1 提取十四行标签与 Hz，写入 `extracted_tables`；不改数。 |
| N04 | `bridge-drawing-registration-reconciliation` | G3 | 冻结坐标公约与鞍点/名义断点两套站；禁止 xmin 平移。 |
| N05 | `bridge-structural-semantic-inventory` | G4 | 两幅独立自由度；通道/门架为耦合，禁止镜像约束。 |
| N06 | `bridge-cad-fem-abstraction` | G5 | 承重索显式；网片/踏板仅质量；禁止从 S10 `.db`/B00/MCT 回写。 |
| N07 | `bridge-fem-topology-geometry-generation` | G6 | 坐标过门：鞍点对齐后恒等变换；节点 X 不得再减 xmin。 |
| N08 | `bridge-material-section-mass-properties` | G7 | 质量 ledger 与图纸/CALC-INPUT 对账；频率提取前必须闭合。 |
| N09 | `bridge-connections-boundaries-supports` | G8A | 支承 NSET 与 `*NODE` 使用同一 \(x\)。 |
| N10 | `bridge-cable-form-finding-initial-state` | G8B | 解析 \(H=wL^2/(8h)\) 只作初值；正式找形看力残差与几何残差；\(h=227.300\) m，不用 255.56 m。 |
| N11 | `bridge-load-cases-combinations-stages` | G9 | `LC-DEAD-PRESTRESS`（NLGEOM）后接 `LC-FREQ`；deck 不得读取 TARGET-FREQ。 |
| N12 | `bridge-elements-mesh-numerical-controls` | G10 | 冻结 `*FREQUENCY` 根数（建议 ≥40，供家族搜索）、观测点集、能量分区。 |
| N13 | `bridge-pre-solve-model-verification` | G11 | 单位、连通、质量、刚体根、坐标门；未过门不得 ccx。 |
| N14 | `bridge-solver-deck-execution` | G12 | 生成/登记 `.inp`，干净目录跑 `ccx`，写 `solver_run_record` 与全部结果哈希。 |
| N15 | `bridge-solution-verification` | G13 | 只从原生 `.dat/.frd` 提取频率与振型；做残差、符号、重根检查。 |
| N16 | `bridge-static-response-code-review` | G14 | 本 QoI 不是规范承载力验算；不得用利用率语言替代频率 delta。 |
| N17 | `bridge-independent-check-sensitivity-credibility` | G15 | 表4-1 ANSYS 是对照源，不是独立复核。独立复核必须另走方法/实现/读图中的两维。无批准容差则只报 delta，不写通过线。 |
| N18 | `bridge-report-audit-change-control` | G16 | 报告数字由机器台账生成；决策词只能是第5节四词。 |

### 1.2 可选未合并名（不是 main 证据）

| 名 | 位置 | 用法 |
|---|---|---|
| `catwalk-step-inp-pipeline` | PR #18 `catwalk-fem/SKILL.md` | 过程别名：STEP→完整 CalculiX deck。在出现真实 `.inp` 并过坐标门之前，不得写成已过门。 |

### 1.3 六个无 `SKILL.md` 的过程标签

| 过程标签 | 绑定实名 | 本协议动作 |
|---|---|---|
| CalculiX evidence audit | N14 + N15 | 检查 `.inp .frd .dat .sta .cvg` 同茎、Actions run、sha256。缺一则 `insufficient`。 |
| Claim-to-artifact trace | N18 | 每行 `qoiId` → `SOLVE-ID` → 文件哈希 → `.dat` 行号 / `.frd` 步。 |
| Experiment preregistration | N01 + N17 | 打开 This study 频率前冻结提取、配对、容差（本协议：容差=未批准）。 |
| failed-run-preservation | N00 + N14 | 失败 `SOLVE-ID` 只读保存，禁止覆盖后宣称成功。 |
| literature-claim-card | N02 + N17 | 表4-1 作成献对照卡：来源、页、单位、是否含振型向量、是否公布容差。 |
| resource-routing-contract | N14 | 正式频率只承认 GitHub Actions（或同等锁定环境）记录的 ccx，不把本机「跑通」写成科学复现。 |

---

## 2. 冻结 QoI 台账（14 行）

单位一律 **Hz**（周期频率，cycles/s）。内部 SI：m, N, kg, s。禁止把 rad/s 或 \(\omega^2\) 填进 This study。

家族码：L/V/T = 横/竖/扭；S/A = 主跨对称/反对称。第 8/9/12 项表内只写 side，**没有** L/V/T。

| qoiId | 表序 | 家族 | \(f_\mathrm{att}\) (Hz) | 提取规则 | 配对规则 | This study |
|---|---:|---|---:|---|---|---|
| QOI-T41-01 | 1 | LS1 | 0.0365 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-02 | 2 | VA1 | 0.0700 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-03 | 3 | LA1 | 0.0726 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-04 | 4 | TA1 | 0.0996 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-05 | 5 | VS1 | 0.1028 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-06 | 6 | LS2 | 0.1087 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-07 | 7 | TS1 | 0.1147 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-08 | 8 | side | 0.1149 | EXT-CCX-FREQ-CYCLES | PAIR-SIDE-ENERGY | 空 |
| QOI-T41-09 | 9 | side | 0.1239 | EXT-CCX-FREQ-CYCLES | PAIR-SIDE-ENERGY | 空 |
| QOI-T41-10 | 10 | VA2 | 0.1438 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-11 | 11 | LA2 | 0.1449 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-12 | 12 | side | 0.1557 | EXT-CCX-FREQ-CYCLES | PAIR-SIDE-ENERGY | 空 |
| QOI-T41-13 | 13 | TS2 | 0.1571 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |
| QOI-T41-14 | 14 | VS2 | 0.1744 | EXT-CCX-FREQ-CYCLES | PAIR-FAMILY-MAC | 空 |

### 2.1 提取规则 `EXT-CCX-FREQ-CYCLES`

1. 仅在 N14 已记录的 `SOLVE-ID` 上执行。作业茎名必须同时存在：`<job>.inp` `<job>.frd` `<job>.dat` `<job>.sta` `<job>.cvg`。
2. 在 `<job>.dat` 定位块 `E I G E N V A L U E    O U T P U T`。读取列 **FREQUENCY (CYCLES/TIME)** 为 \(f\)（Hz）。禁止只读 EIGENVALUE 再自行换算（\(2\pi\) / \(4\pi^2\) 误换是已知失败模式）。
3. 在 `<job>.frd` 读取同阶 `100CL` 频率头，要求 \(|f_\mathrm{dat}-f_\mathrm{frd}|\le 10^{-6}\,\mathrm{Hz}\) 或相对差 \(\le 10^{-8}\)。
4. 振型取该步 `DISP`（U1,U2,U3），坐标必须已是 `CS-CATWALK-CHAINAGE`。
5. `<job>.sta` 须显示 FREQUENCY 步完成；其前一 NLGEOM STATIC 步须在 `.cvg` 中有可解析残差。
6. 刚体或近零根（建议 \(|f|<10^{-4}\) Hz 且能量无结构主导）不得写入十四项。
7. 理论 \(\eta/\varepsilon/k_c\)、L0 \(f_n=n\sqrt{g/32h}\)、PR #17 反标根，一律不得写入 This study。

解析器输出每根至少：`solveId, jobStem, modeIndexInDat, f_dat_Hz, f_frd_Hz, datByteOffset, frdStepId, sha256_dat, sha256_frd`。

### 2.2 配对规则

**PAIR-FAMILY-MAC（有 L/V/T 的 11 项）**

1. 在注册观测集 \(\mathcal{O}\) 上投影振型（同一站、同一分量、同一尺度）。建议 \(\mathcal{O}\)：两幅面层索在门架/通道站的 UY、UZ；扭转用两幅竖向差动或截面转角代理。
2. 能量分类：\(E_L,E_V,E_T,E_\mathrm{dist},E_\mathrm{portal},E_\mathrm{N660},E_\mathrm{main},E_\mathrm{S717},E_\mathrm{S503}\)。主导方向 = \(\arg\max(E_L,E_V,E_T)\)，且该向占比 ≥ 0.45；否则标 `MIXED`，不得强贴 L/V/T。
3. 主跨奇偶：沿主跨（鞍点 \(x=666.679\) 至 \(2953.321\)）对主导分量做半波计数；奇=A，偶=S。与表标签冲突则 `not-comparable`，禁止改用频率邻近重贴。
4. 共同/差动：两幅交换算子 \(P_\pm\)；差动主导才允许进入 T 族候选。
5. MAC（有附件向量时，公共观测 + 参考质量 \(M_\mathrm{ref}\)）：
   \[
   \mathrm{MAC}(\hat\phi_a,\hat\phi_b)=\frac{(\hat\phi_a^T M_\mathrm{ref}\hat\phi_b)^2}{(\hat\phi_a^T M_\mathrm{ref}\hat\phi_a)(\hat\phi_b^T M_\mathrm{ref}\hat\phi_b)}.
   \]
   近重根用子空间主角度，不逐阶强跟。
6. 配对代价：\(C=w_E\Delta E+w_p\Delta\mathrm{parity}+w_\pm\Delta\eta_\pm+w_M(1-\mathrm{MAC})+w_f|\Delta f|/f_\star\)，其中 \(w_f\) 最小。\(f_\star=0.1\) Hz 只作无量纲尺度，**不是容差**。
7. 附件若只有振型图、没有机器可读向量：MAC 项删除，`macStatus=not-comparable`；仍必须完成家族/奇偶/能量配对。不得把「频率最近」写成配对成功。

**PAIR-SIDE-ENERGY（表序 8/9/12）**

1. 表标签只有 side。诊断别名 SIDE1/2/3 来自理论档，**不是**表4-1 原文。
2. 判定 SIDE：主跨外能量占比 ≥ 0.50，且主导跨为 {北 660, 南辅 717, 最南 503} 之一。
3. 理论候选映射（717→0.1149，660→0.1239，503→0.1557）只作待证假设。未用振型确认跨域前，这三行最多 `delta-reported` 且必须标注 `conditional-span-map`。
4. 禁止因频率靠近 TS1（0.1147）就把 0.1149 配成扭转。

**禁止**

- 只按表序 = CalculiX 第 \(k\) 个非刚体根。
- 「严格前14阶同序」与「家族级匹配」混称。后者允许在前 40–60 根中找标签，不得叫「附件前14阶已复现」。
- 用最近频率填无可靠物理匹配的行。该行决策 = `not-comparable`。

### 2.3 对照源隔离

| 源 | 数值 | 角色 |
|---|---|---|
| SRC-ATT23-T41 | 上表 14 个 Hz | 唯一比对参照 |
| SRC-ATT-OTHER-FREQ-0296 | 0.0296…0.1187 | 隔离；与表4-1 不是同一张表 |
| 理论 L0 / ηεkc / PR #17 | 任意根 | 可作独立方法，**不是** This study |

附件 ANSYS 不得既当「真值」又当「独立复核」。本协议把它定为 **literature referent**（N17 第10条：用途相容的已发表模型）。独立复核必须另选：解析/降阶（方法独立）或第二脚本/第二求解器（实现独立），并独立读图（数据解释独立）。三维中至少满足两维。

---

## 3. 证据合同

「符合」之前，下列全部必须存在、只读、可复放。当前：**全部缺失 → `insufficient`**。

### 3.1 必备文件（同作业茎）

| 文件 | 证明什么 | 最低检查 |
|---|---|---|
| `<job>.inp` | deck 含 `*FREQUENCY`，坐标公约在 `*HEADING`，无 TARGET-FREQ 数字 | 含 `K16+876`；不含 `255.56`；`xmin_shift_used=false` |
| `<job>.dat` | 原生特征值文本 | 存在 CYCLES/TIME 表 |
| `<job>.frd` | 频率步 + DISP | 与 .dat 频率交叉核对 |
| `<job>.sta` | 步完成 | FREQUENCY 步结束 |
| `<job>.cvg` | 前序静力收敛 | NLGEOM 残差可解析 |
| `solver_run_record.json` | N14 运行记录 | solver、version、deckHash、exitStatus、resultFiles |
| `raw_result_manifest.json` | 原始结果登记 | 每文件 sha256、字节数、MIME |
| `checksums.sha256` | 发布校验 | 与文件逐项一致 |

另需：`coord_gate.json`（恒等变换、鞍点残差）、`pre_solve_verification.json`、`solution_verification_report.json`。

### 3.2 哈希与 Actions

1. 对上述每个文件算 SHA-256（小写 hex，可带 `sha256:` 前缀）。
2. `deckHash` = `.inp` 内容哈希；结果哈希不得在后处理改写后重算冒充原始。
3. 正式 run 必须有 GitHub Actions：`run_id`、`commit` SHA、workflow 文件、`ccx` 安装步骤、artifact 名。参考既有扎青命令流（`.github/workflows/zhaqing-native-command.yml`）的「checkout → 装 ccx → 跑 → upload-artifact → 回写 runId」，但必须指向猫道作业，不得复用扎青 artifact。
4. 当前 `main` 无猫道频率 workflow；PR #18 无 Actions 产物 `.inp`。在新 workflow 跑通前，不得填哈希占位符。
5. commit 必须包含生成该 `.inp` 的脚本/IR，且坐标门测试证明未减 xmin。

### 3.3 现况（协议冻结日）

| 项 | 事实 |
|---|---|
| `main` | 无 `catwalk-fem/`，无 `.inp` |
| PR #18 | 有 `write_inp` 代码；`artifacts/` 仅 `.gitkeep` |
| 理论 PR #16/#17 | 有表4-1 与 ηεkc；**不是** ccx 输出 |
| This study | 全部 `null` |

---

## 4. 容差 / 验收（预注册，禁止事后放宽）

预注册结论（N17 规则 1 与 5）：

1. **附件2-3 未公布频率容差。** 本章程 **不批准** 任何 Hz 或 % 通过线。
2. 因此正式验收动作只有：在配对成功后计算
   - \(\Delta f = f_\mathrm{this}-f_\mathrm{att}\)（Hz，有符号）
   - \(|\Delta f|\)（Hz）
   - \(\delta = \Delta f/f_\mathrm{att}\)（\(f_\mathrm{att}>0\)）
   并写入台账。 **不画 PASS/FAIL 行。**
3. 理论档曾建议「平均 5%、最大 10%、T 族 7.5%」。该建议 **未** 进入本章程，**不得** 用作本比对通过准则，也不得在看见 This study 后再启用。
4. 禁止事后放宽：不得因偏差大而改配对规则、改观测集、改「最近频率」、或把 SIDE 改贴成 L/V/T。改规则必须新 charter 版本 + 新 runId。
5. 近零量不用相对误差作唯一指标；本表最小 \(f_\mathrm{att}=0.0365\) Hz，相对误差可报，但判定词仍不得变成通过。
6. 网格/步长敏感性按 N12/N15 预注册 control metrics 做，不得求解后改换更稳的指标。

「符合」的未来门（此刻不可用）：证据合同闭合 **且** 章程另文批准容差 **且** 十四行均家族配对成功 **且** 未舍入 delta 落入该容差。缺任一条件保持禁止。

---

## 5. 决策词汇

只许四词。报告摘要与 JSON `decision` 用同一枚举。

| 词 | 何时使用 | 此刻 |
|---|---|---|
| **insufficient** | 缺 `.inp/.frd/.dat/.sta/.cvg`、缺 commit/Actions、缺 sha256、或 This study 非原生 `*FREQUENCY`。 | **当前全章** |
| **not-comparable** | 证据在，但坐标系/阶段/质量基准不同，或家族/奇偶/SIDE 能量冲突，或只能靠阶次对齐。 | 有 ccx 后按行使用 |
| **delta-reported** | 证据在、配对成立（或 SIDE 条件映射已标明）、已报三种 delta、**无** 通过线。 | 有合格提取后的最高允许词 |
| **符合** | 第4节未来门全满足。 | **禁止** |

禁止同义替换：「基本一致」「工程上可接受」「仅超出很少」「已复现十四阶」。

N17/N18 gate 词 `PASS/BLOCKED` 是流程状态，不是表4-1 符合。G15 在无独立方法、无容差时应为 `BLOCKED` 或「仅发布 delta 对照，不发布验证通过」。

---

## 6. 中文方法草案（15 句）

本章把 CalculiX 原生 `*FREQUENCY` 输出与附件2-3表4-1十四项频率放在同一物理量、同一坐标系和同一成型态上对照，不把 η/ε/kc 理论根或任何反标根当作 This study。坐标公约预先写成 \(x=\)桩号减去 \(K16+876.000\)（米，北向南为正）；鞍点对齐后只允许恒等变换，禁止再用 STEP 最小 \(x\) 去对站。This study 只能从已记录 ccx 运行的 `.dat` 特征值表 CYCLES/TIME 列读取，并用同茎 `.frd` 频率头交叉核对。在 `.inp`、`.frd`、`.dat`、`.sta`、`.cvg`、commit、Actions 与 sha256 齐备之前，This study 单元格保持空值。表4-1没有公布频率容差，按独立复核节点规则，未经章程批准的限值不得写成通过或不通过，只能报告有符号差、绝对差和相对差。模态配对必须先用横/竖/扭与对称/反对称家族，再加上注册观测集上的能量、奇偶或 MAC，禁止只按频率阶次对齐。表中第8、9、12项仅标注 side，没有 L/V/T，只能按边跨能量局域化配对；717/660/503 米映射只是理论候选，不是表内标签。附件2-3的 ANSYS 结果是已发表对照源，不得同时充当独立复核；独立复核必须另走降阶理论或第二实现，并独立读图。PR#18 隔离文件里 0.0296 起算的十四个数与表4-1不是同一张表，求解器不得读取任一张目标频率表。当前主分支与 PR#18 产物目录都没有真实 `.inp`，因此全章决策词固定为 insufficient。符合一词在证据合同未闭合且章程容差未批准前禁止出现。预测十四项必须在打开表4-1数值之前冻结并计算哈希。质量账、索力初态、坐标门和静力残差未通过时，不得进入频率提取。近重根与避交用子空间主角度跟踪，不以阶号判断模型跳错。报告中每个对照数字回链到 qoiId、SOLVE-ID 与文件哈希；失败运行原样保存，不得覆盖后改称成功。

---

## 7. 给邻章机器人的问题

### 7.1 给 Related Works bot

1. 附件2-3表4-1的十四项是风洞实测、ANSYS 计算，还是二者混排？请给页码与原文措辞，不要推断。
2. 除频率外，是否公布机器可读振型向量，还是只有图4-5/4-8之类插图？哪些阶有图？
3. 全报告是否出现任何频率容差、MAC 阈值或「符合」判据？若无，请明确写「未公布」。
4. 0.0296…0.1187 与 0.0365…0.1744 两套十四频分别出自哪一表/哪一版？二者能否在文献上区分，避免写成同一 TARGET。
5. 既有猫道/悬索文献用家族标签、MAC 还是阶次对齐？有无「对照源不得兼独立复核」的先例表述可引。
6. 请做 literature-claim-card：表4-1 每行的来源句、是否含振型、是否含容差；不要把 ANSYS 写成 ground truth。

### 7.2 给 Experiment bot

1. 是否已有过坐标门的真实 `.inp`（恒等变换，未减 xmin）？若无，This study 必须保持空，不要填理论根。
2. 计划的 `*FREQUENCY` 根数、作业茎名、ccx 版本、Actions workflow 文件名是什么？
3. 提取是否只读 `.dat` 的 CYCLES/TIME，并与 `.frd` 的 `100CL` 交叉核对？请给出解析脚本路径，禁止手抄。
4. 观测集 \(\mathcal{O}\) 与能量分区（主跨/660/717/503、L/V/T、共同/差动）是否在求解前写入 `mesh_plan`/`numerical_controls`？
5. 第8/9/12项准备按 PAIR-SIDE-ENERGY 做条件映射，还是宣布 not-comparable 直到有振型？不要默认 717/660/503。
6. 如何保证 write_inp / ccx 不读取 `isolated/TARGET-FREQ.json` 或表4-1？
7. 证据包将上传哪些文件名？请预留 `checksums.sha256` 与 `solver_run_record.json` 字段，失败 SOLVE-ID 不覆盖。
8. 在 Actions `run_id` 出现前，实验结果表是否同意整表写 `insufficient`、不出现「符合」？

---

## 附录 A — 执行清单（Experiment 可照做）

```text
[ ] N01 charter：intended use + 无容差只报 delta
[ ] N02 附件2-3 PDF sha256；隔离 0.0296 表
[ ] N04/N07 坐标门 JSON：identity，saddle residual
[ ] N13 预求解 PASS 或有界且不阻断频率用途
[ ] N14 ccx 在 Actions；五文件 + 哈希
[ ] 先写 predicted_modes.json（无 f_att）并哈希
[ ] 再加载 SRC-ATT23-T41
[ ] 家族/SIDE 配对；禁止阶次对齐
[ ] 写 delta 三列；decision ∈ {insufficient, not-comparable, delta-reported}
[ ] 不写 符合
```

## 附录 B — 坐标与隔离（给 N07/N14）

```
x_m = chainage_m - 16876.000
# 北塔鞍点 666.679 m，南塔鞍点 2953.321 m（CALC-INPUT）
# 名义断点 0, 660, 2960, 3677, 4180 只作审计，不静默替换鞍点
# 禁止: x = X_step - min(X_step)
```

TARGET-FREQ / TARGET-SHAPE 必须放在求解器不可读目录；冻结时单独哈希。
