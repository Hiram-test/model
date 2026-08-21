# η / ε / k_c 图纸候选与十四频快算

本文只做三件事：把用户可见仓库里**全部 Pull Request**的文件清单过一遍；从实际读到的张靖皋猫道图纸给出 η、ε、k_c 的构造区间；用 **v3 原文公式**分别算出 14 个根，和锁定的 F_att 对表。

不改 v3 正文。不用 227.30 m。不从 F_att 反标参数。不把表 4-1 嵌进求解。

锁定量：

- F_M = 255.56 m（用户锁定；1225 MD0-01 该尺寸标在页面上部主缆立面，下部猫道立面未重复标注）
- F_att = {0.0296, 0.0301, 0.0601, 0.0608, 0.0714, 0.0733, 0.0735, 0.0873, 0.1012, 0.1012, 0.1098, 0.1102, 0.1155, 0.1187} Hz

v3 三个未锁参数的含义：

- **η**（M2）：EA = η (EA)_upper，钢丝绳工作点轴向刚度
- **ε**（M7）：k_p = ε k_bend，面层—门架顶部连接
- **k_c**（M8）：两幅耦合；可用 M9 的 k_fixed 上界乘接口折减 ε_c

公式与常数一律取自 `猫道第14阶扭转模态_纯力学理论模型族_逐层计算与谱序解释_v3.txt`（#16 / 33662f98）。本文件只引用，不改写。

---

## 1. 可见仓库与私库

当前 GitHub 身份是 `Hiram-test`。公开仓库正好三座：

| 仓库 | 可见性 | 默认分支 | PR 数 |
|---|---|---|---|
| [Hiram-test/model](https://github.com/Hiram-test/model) | public | main | #1–#16（连续） |
| [Hiram-test/agentic](https://github.com/Hiram-test/agentic) | public | main | #1–#4 |
| [Hiram-test/demo-rl-calculix](https://github.com/Hiram-test/demo-rl-calculix) | public | main | #1–#10、#17–#35；**#11–#16 返回 404** |

私库：`gh api user/repos` 被 integration token 以 403 拒绝；`search_repositories user:Hiram-test` 只返回上述三座公开仓；本 Cloud 环境 `repos` 也只有 `github.com/Hiram-test/model`。因此**本身份看不到任何私库 PR**，无法在私库文件列表里找图纸。

材料不在默认分支树里。下面按 PR 文件列表检索：`图纸汇总`、`1225.pdf`、`MD0`、`M00`、`M04`、`M05`、`猫道图纸`。

---

## 2. Hiram-test/model 全部 PR

| # | 状态 | 标题 | 图纸关键词命中 |
|---|---|---|---|
| [1](https://github.com/Hiram-test/model/pull/1) | closed | Add audited catwalk execution log and full 3D next-step plan | 无 PDF。日志提到 124 页 1225、E=110 GPa 试算、MD1-06 缺页 |
| [2](https://github.com/Hiram-test/model/pull/2) | closed | Document CAD Skill gate lessons and assembly audit case | **扎青** DWG，另一座桥 |
| [3](https://github.com/Hiram-test/model/pull/3) | closed | docs: add catwalk automation execution log and next-step plan | 同 #1，无图纸 PDF |
| [4](https://github.com/Hiram-test/model/pull/4) | closed | Publish installable Skill Suite and remove invalid CAD outputs | 扎青 DWG 迁到 `source-inputs/`；无张靖皋施工图 |
| [5](https://github.com/Hiram-test/model/pull/5) | closed | Document Skill Gate fidelity failure | 无图纸 |
| [6](https://github.com/Hiram-test/model/pull/6) | open draft | feat: enforce Bridge FEM node and Gate lifecycle | 无图纸 |
| [7](https://github.com/Hiram-test/model/pull/7) | open draft | Document proxy-box failure and staged geometry assembly | 无图纸 |
| [8](https://github.com/Hiram-test/model/pull/8) | open draft | feat: add Zhaqing CAD reference model | 扎青 CAD，无张靖皋图纸 |
| [9](https://github.com/Hiram-test/model/pull/9) | open draft | build Zhaqing CAD-003 from frozen DWG evidence | **扎青** 预应力/CAD，不用 |
| [10](https://github.com/Hiram-test/model/pull/10) | open draft | archive: preserve Zhangjinggao bridge dataset | 清单/脚本。图纸本体在 Release `zhangjinggao-full-20260729`，不在 PR blob |
| [11](https://github.com/Hiram-test/model/pull/11) | closed draft | Audit published and draft STEP Releases | 无图纸 |
| [12](https://github.com/Hiram-test/model/pull/12) | closed draft | Inventory Release assets for cross-passage design evidence | workflow 从 `archive-0050.tar.zst` 抽出 `*00张靖皋长江大桥南航道桥猫道图纸1225.pdf` 与复核报告 |
| [13](https://github.com/Hiram-test/model/pull/13) | open draft | isolate prestress calibration on verified Zhaqing L2 model | 扎青预应力 |
| [14](https://github.com/Hiram-test/model/pull/14) | open draft | calibrate Zhaqing L2 completed-state prestress | 扎青预应力 |
| [15](https://github.com/Hiram-test/model/pull/15) | open | validate Zhaqing completed-state main-cable prestress | 扎青预应力 |
| [16](https://github.com/Hiram-test/model/pull/16) | open draft | Add catwalk thirteen-model theory archive | **猫道理论** v3/v1.2/zip（33662f98）。无施工图 PDF |

#16 文件列表（理论包，不是施工图）：

- `猫道第14阶扭转模态_纯力学理论模型族_逐层计算与谱序解释_v3.txt`
- `张靖皋猫道第14阶扭转模态_十三个纯力学理论模型公式与逐层计算_v3.pdf`
- `猫道十四项模态_纯力学简化族与直接计算规律_v2.txt`
- `张靖皋猫道十四项低阶模态_独立理论建模与理论验证_v1.2.txt` / `.tex` / `.pdf`
- `张靖皋猫道理论验证_可复现包_v1.2.zip`

v1.2 原文写明新源文件是《图纸汇总-2026.08.05.pdf》（175 页，SHA-256 `5b6231a766c549db07539df85d8c14b99b816dc0772abb1ab19d7deb782b0bd9`），并写该 175 页 PDF **未进入归档**。#16 文件列表里没有这份 PDF，也没有 M00/M04 后期图。

#9 / #13 / #14 / #15 全部是扎青。不参与 η / ε / k_c。

---

## 3. Hiram-test/agentic 全部 PR

| # | 状态 | 标题 | 图纸 |
|---|---|---|---|
| [1](https://github.com/Hiram-test/agentic/pull/1) | closed | BridgeMind 1.1.0：接通 BSDL 经验读回链 | 无 |
| [2](https://github.com/Hiram-test/agentic/pull/2) | closed | BridgeMind 1.1.0 最终版：完成 BSDL 经验读回链 | 无 |
| [3](https://github.com/Hiram-test/agentic/pull/3) | open | CalculiX .inp 兼容导入 | 无 |
| [4](https://github.com/Hiram-test/agentic/pull/4) | open | 资源法：按权力分工 | 无 |

四个 PR 的文件是 zip / workflow / 法律文档。没有 1225、图纸汇总、MD0、M00、M04、M05。

---

## 4. Hiram-test/demo-rl-calculix 全部 PR

已列出 #1–#10、#17–#35。#11–#16 对 API 为 404（编号空缺，不是权限墙）。

| 已知关注 | 文件列表结论 |
|---|---|
| [#24](https://github.com/Hiram-test/demo-rl-calculix/pull/24) 通道扭转五方法 | CalculiX/mesh 实验，无张靖皋施工图 |
| [#34](https://github.com/Hiram-test/demo-rl-calculix/pull/34) draft P–H routing | 实验脚本与 CSV，无施工图 |
| [#20](https://github.com/Hiram-test/demo-rl-calculix/pull/20) FEA case library | markdown 案例库，无 1225 / 图纸汇总 |

其余 demo PR 文件名检索 `图纸|1225|MD0|M00|M04|M05|猫道|dwg|张靖`：只有 #17 的 CalculiX 诊断 PDF，与张靖皋猫道施工图无关。

---

## 5. 实际读到的图纸（Release，不是 PR blob）

PR 文件列表里**没有**施工图 PDF。#10 / #12 指向 Release [`zhangjinggao-full-20260729`](https://github.com/Hiram-test/model/releases/tag/zhangjinggao-full-20260729)。从 `archive-0001.tar.zst`（与 0047/0050 同套）抽出并读图：

| 文件 | 归档路径 | SHA-256 | 页数 |
|---|---|---|---|
| 1225 猫道施工图 | `01_设计资料与规范/00张靖皋长江大桥南航道桥猫道图纸1225.pdf` | `8df26c6b04f652b952e6cdf9575f34e76c8d014cbb61edf0b846c1c75d8bc113` | 124，A3 |
| 复核报告 0324 | `01_设计资料与规范/张靖皋长江大桥南航道桥 猫道结构复核计算报告0324.pdf` | `8b2f0eb267216cd7d1e9746adb28f8973b4614d27fa1e2290eb12c2a6a45ca90` | 118，A4 |

1225 的 SHA 与 #16 zip 内 `evidence/drawing1225_evidence.md` 一致。归档目录检索不到《图纸汇总-2026.08.05.pdf》、M00-01、后期 M04（1123 kg / M1·M2）。

已读页面：目录 p.1–4；MD0-01 p.6；MD0-02 p.7；MD4-01 p.91；MD4-02 p.92；MD5-01 p.98；MD5-02 p.99；MD5-09 p.106。复核报告 1.4（材料）、4.4（横向通道）、4.5（门架）。

### 5.1 1225 MD0-01（p.6）— 索表，无 EA，无工作张力

| 名称 | 规格 | 结构 | 强度 | 破断 | 线质量 |
|---|---|---|---|---|---|
| 面层承重索 | φ50 ×16 | CFRC8×36WS | 1960 MPa | 2380 kN | **12.038 kg/m** |
| 上扶手索 | φ36 ×2 | 6×36WS+IWR | 1870 MPa | 863 kN | 5.42 kg/m |
| 中、下扶手 | φ20 ×4 | 6×36WS+IWR | 1870 MPa | 266 kN | 1.67 kg/m |
| 门架承重索 | **φ54 ×6** | 6×36WS+IWR | 1960 MPa | 2030 kN | 12.2 kg/m |

跨度 660+2300+717+503 = 4180 m。门架单幅 11+41+11+8 = 71。本 PDF 的 MD5 只画 H1–H12（跨中及以南）。21 道全桥链在复核报告 / 抗风报告，不在这本 1225。

255.56 m 标在上部主缆立面，不是猫道承重索垂度标签。计算仍按用户锁定 F_M = 255.56 m。由此

```
c0 = L_M √(g / 8 F_M) = 159.29302 m/s
L_e = 2375.7228 m
H0 = μ_M c0² ≈ 8.39345×10⁶ N
```

**禁止改用 227.30 m。**

### 5.2 1225 MD4 / MD5 — 门架与通道接口

- MD4-01/02：门架 □160×160×4，Q235，**829.3 kg 不含底梁**，高度约 7.5–8.3 m。螺栓 6/7/8。本版 **没有 M1/M2、没有 1123 kg**。
- MD5-01/02：通道长约 49.65–49.92 m，B = 42.90 m，倒三角桁架 φ152×6。
- MD5-09：法兰 M20×8.8、吊耳。接口是 **U 形螺栓 / 抱箍**，不是刚接刚架。

法兰本身是杆件—杆件硬连接；软的是 **桁架端 → 索** 的 U 栓/抱箍/铰。

### 5.3 复核报告 1.4 — 设计输入 EA（不是 F_att）

承重索设计：E = **1.20×10⁵ MPa**，A = **1400.42 mm²**（φ50 CFRC8×36WS+IWRC）；一根“智慧芯” A = 1292.45 mm²。

```
EA_report = 15×120 GPa×1400.42 mm² + 120 GPa×1292.45 mm²
          = 2675.850 MN
```

门架索在**本报告**写成 φ50，与 1225 的 φ54 冲突。η 只使用面层 16 索的报告 EA，不混门架索。

### 5.4 复核报告 4.4–4.5 — 节点语义，无数值 k_p / k_c

- 门架：上横梁 U 栓连门架索，底梁 U 栓连面层索；**立柱与上横梁、底梁铰接**。
- 通道：尾段 U 栓吊在面层索上；立柱—上横梁铰接；下端 **抱箍+铰链** 连桁架上弦。

图纸和报告都**没有**给出 k_p、k_c、工作点切线 EA。

---

## 6. 从图纸读 η / ε / k_c（禁止 F_att 反标）

### 6.1 η

v3：

```
A_μ = 12.038 / 7850 = 1.53350×10⁻³ m²
(EA)_upper = 16 E_s A_μ = 5.05443 GN
EA = η (EA)_upper
```

1225 **不给 EA**。复核报告给设计 E、A，那是静力设计输入，不是现场切线刚度，也不是频率反标。

```
η_report = 2675.850 MN / 5.05443 GN = 0.5294 ≈ 0.53
```

三档（构造区间，不是拟合）：

| 档 | η | 依据 |
|---|---|---|
| 软 | 0.40 | 施工伸长更大：约 E≈90 GPa × A_nom/A_μ 量级，仍远低于钢上界 |
| **中（推荐）** | **0.53** | 复核报告设计 EA / v3 质量等效钢上界 |
| 硬 | 0.70 | 少伸长，但仍 < 1 |

**不用 η = 0.1。** v3 表在 η=0.1 时第一移动根落到 0.0729 Hz，那是参数扫描，不是图纸。

### 6.2 ε

v3：k_bend = 6.49811×10⁵ N·m/rad，k_p = ε k_bend。

图纸：双铰 + U 栓/抱箍，相对弯曲远低于实心立柱。取构造带 1% / 3% / 10%，**不是**为了打中 0.07 或 0.11。

| 档 | ε | k_p / (N·m/rad) | k_d = 41 k_p / L_M |
|---|---|---|---|
| 软 | 0.01 | 6.498×10³ | 1.158×10² |
| **中** | **0.03** | **1.949×10⁴** | **3.475×10²** |
| 硬 | 0.10 | 6.498×10⁴ | 1.158×10³ |

v3 已算出（本轮复算一致）：

| ε | f1− | f1+（光学，本任务取这一根） |
|---|---|---|
| 0.01 | 0.029592 | 0.070441 |
| 0.03 | 0.029656 | **0.111566** |
| 0.10 | 0.029680 | 0.196612 |

软档光学根靠近 0.0735，**不因此改推软档**。中档光学根在 0.11，对应 F_att 的 0.1155 一带。

### 6.3 k_c

v3 M9：两端固结、49.655 m 通道

```
k_fixed = 12 E_s I_passage / 49.655³ = 1.07058×10⁵ N/m
```

实际端头是 U 栓 + 铰 + 抱箍，必须乘接口折减 ε_c。法兰（MD5-09）不是这个软接口。

| 档 | ε_c | k_c 离散 = ε_c k_fixed | k_c 均匀化 = 13 k_c / L_M |
|---|---|---|---|
| 软 | 0.01 | 1.071×10³ N/m | 6.05 N/m² |
| **中** | **0.03** | **3.212×10³ N/m** | **18.15 N/m²** |
| 硬 | 0.10 | 1.071×10⁴ N/m | 60.5 N/m² |

k_c 进入 M8 差动截止，不单独再解一条“第 14 根”。十四频里与通道有关的单点是 **M9 质量打开后的相对分裂第二根**。

---

## 7. 推荐的三组候选

| | η | ε | ε_c | k_p | k_c 离散 | k_c 均匀化 |
|---|---|---|---|---|---|---|
| 软 | 0.40 | 0.01 | 0.01 | 6.498×10³ N·m/rad | 1.071×10³ N/m | 6.05 N/m² |
| **中（推荐）** | **0.53** | **0.03** | **0.03** | **1.949×10⁴** | **3.212×10³** | **18.15** |
| 硬 | 0.70 | 0.10 | 0.10 | 6.498×10⁴ | 1.071×10⁴ | 60.5 |

中档的 η 有复核报告 EA 作分子；ε 与 ε_c 是同一级接口释放（铰+U 栓），没有理由一个取 0.03、另一个取 1.0。

---

## 8. 各模型单点（v3 公式，分开算，不耦合成一个大特征值）

常数：L_M=2300，g=9.80665，μ_M=330.78584，H0≈8.39345×10⁶，L_e=2375.7228，k_bend=6.49811×10⁵。M6 取 (α,β)=(0.5, 0.7)。

### 8.1 M6 慢扭转 n=1–4

与 v3 表一致：

```
0.0295694,  0.0593077,  0.0889414,  0.1184655 Hz
```

### 8.2 M9 质量打开的第二根

v3 §10.4：n=1 两支相对分裂 1.792%。v3 同时写明“绝对频率不能只靠附加质量修正”。本任务要的是**分裂第二根**，不是把 γ 系数乘到 M6 上去压低绝对频率。

```
f_M9,n=1 = 0.0295694 × (1 + 0.01792) = 0.030099 Hz
```

同一公式的 n=2 为 0.0593077 × 1.01714 = 0.060324 Hz。用户只要一根“第二根”时，只认 n=1 → 0.0301。n=2 可作旁注，不把它当成 F_att 拟合。

若误用 γ 系数压绝对频率，得到 0.028785 / 0.029301，两根都低于 0.0301，那是另一套解释，本文不用。

### 8.3 M2 偶数根 + 该 η 下第一移动根

N=40 Galerkin，复现 v3 §3.3 全表（η=0.1/0.3/0.5/0.7）。偶数 2f_01 = **0.069258 Hz，与 η 无关**。奇数子空间第一移动根：

| η | 第一移动根 / Hz |
|---|---|
| 0.40 | 0.095693 |
| **0.53** | **0.096802** |
| 0.5294（报告 EA） | 0.096799 |
| 0.70 | 0.097491 |

奇数张弦极点（0.034629、0.103887）不是根，不列入。

图纸 η 把移动根放在 **0.096–0.098 Hz**，进不了 0.073 簇。这是预期，不是算错。

### 8.4 M7 光学第一根

见 §6.2。中档 ε=0.03 → **0.111566 Hz**。

### 8.5 M1 / M11 南辅跨

- M1：c0 / (2×717) = **0.111083 Hz**
- M11 慢波、γ=100、第 5 根：**0.100109 Hz**（v3 列出）
- M11 c0、γ=1000、第 4 根：**0.110377 Hz**
- M11 c0、γ=100 的 0.105125 Hz 未对上任何 F_att 单点，不硬塞

---

## 9. 十四行对表（中档主表）

一行一个模型，不联立。相对误差 (calc − F_att) / F_att。|误差|≤5% 记 Y。

| # | F_att / Hz | 模型 | 计算 / Hz | 相对误差 | ≤5% |
|---|---|---|---|---|---|
| 1 | 0.0296 | M6 n=1 | 0.029569 | −0.10% | Y |
| 2 | 0.0301 | M9 n=1 质量相对分裂第二根 | 0.030099 | ≈0% | Y |
| 3 | 0.0601 | M6 n=2 | 0.059308 | −1.32% | Y |
| 4 | 0.0608 | — | 没单点 | — | 没单点 |
| 5 | 0.0714 | M2 偶数 2f_01 | 0.069258 | −3.00% | Y |
| 6 | 0.0733 | M2 第一移动根 η=0.53 | 0.096802 | **+32.1%** | N |
| 7 | 0.0735 | — | 没单点 | — | 没单点 |
| 8 | 0.0873 | M6 n=3 | 0.088941 | +1.88% | Y |
| 9 | 0.1012 | M11 慢波 γ=100 第 5 根 | 0.100109 | −1.08% | Y |
| 10 | 0.1012 | — | 没单点 | — | 没单点 |
| 11 | 0.1098 | M1 南辅跨 | 0.111083 | +1.17% | Y |
| 12 | 0.1102 | M11 c0 γ=1000 第 4 根 | 0.110377 | +0.16% | Y |
| 13 | 0.1155 | M7 光学 f1+ ε=0.03 | 0.111566 | −3.41% | Y |
| 14 | 0.1187 | M6 n=4 | 0.118466 | −0.20% | Y |

**中档：10 根 ≤5%，1 根明显偏离（M2 移动根），3 个没单点。**

旁注（不算进主分）：M9 n=2 相对分裂 = 0.060324 Hz，对 0.0608 为 −0.78%。若把这根算进去，没单点减 1，仍改变不了第 6 行的 +32%。

软档若把 M7(ε=0.01)=0.070441 对 0.0735（−4.16%），光学根就离开 0.1155，第 13 行变没单点；M2 移动根仍是 +30%。**不把软档升为推荐。**

硬档 M7(ε=0.10)=0.196612，对 0.1155 为 +70%。更差。

第 6 行失败的原因：图纸 η≈0.53 时 Irvine 第一移动根已经越过 0.07，停在 0.097。要把它按回 0.073，只能把 η 压到 ~0.1，那是 **F_att 反标**，本文拒绝。0.0733 / 0.0735 在当前图纸深度下没有第二个独立单点（除非动用未归档的《图纸汇总》M04/M00 重读门架质量与接口）。

---

## 10. 没找到什么

| 目标 | 结果 |
|---|---|
| 《图纸汇总-2026.08.05.pdf》 | **三仓全部 PR 文件列表都没有**；July 29 归档也没有。v1.2 已声明未归档 |
| M00-01 及后期 M04–M05（1123 kg、M1/M2、□160×6/8） | 只存在于 v1.2 对 175 页图的转录，本轮不能当一手图 |
| 1225 本体 | 不在任何 PR blob；在 Release 归档。已读 |
| 工作点切线 EA、安装索力 | 1225 与复核报告都没有 |
| 数值 k_p、k_c | 只有铰/U 栓/抱箍语义 |
| 私库图纸 | 本 token 不可见 |

要把中档第 6 行从“没对上”变成“有图”，需要把 175 页《图纸汇总》或含 M00/M04 后期图的私库/Release 放到可见位置。在那之前，η=0.53、ε=0.03、ε_c=0.03 仍是图纸能支持的唯一推荐组。
