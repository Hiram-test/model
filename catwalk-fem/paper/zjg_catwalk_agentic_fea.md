# 张靖皋施工猫道的 Agentic 有限元翻模

**三张哈希、41fb3222 连通定义表、以及新主 deck 上可分解但未收敛的第一增量**

Run `cursor/catwalk-main-deck-bound-4c2c`。仓库 `Hiram-test/model`，PR #19。
几何：Release `catwalk-attachment23-v2.0-s10-20260716`
`cw_S10_0716t050342_a4_centerline.step` SHA-256 `d03d01e38b823df5af4c1ff9b0b175fdfb87b097b9cda9a03af5d14e9c763344`。
门架计数单位是「榀」（U+6980），不是「榌」（U+698C）。

三张哈希角色分开。前两张**不改写**：

| 角色 | 路径 | SHA-256 | 字节 |
|---|---|---|---:|
| ELSET+单轴失败现场 | `artifacts/zjg_catwalk_coarsened.inp` | `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da` | 7 702 117 |
| IC 过门 / 第一增量奇异现场 | `artifacts/zjg_catwalk_ccx221.inp` | `41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a` | 26 839 981 |
| **新主 deck** | `artifacts/zjg_catwalk_main.inp` | `c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84` | 47 948 333 |

## 摘要

本文记录张靖皋施工猫道一次可审计的端到端 agentic 有限元翻模。77 MB 毫米制中心线 STEP 映射到 \(x=\text{桩号}-K16+876.000\)。面层锚与门架锚分属不同 `*NSET` / `*BOUNDARY`，交集为空。21 道横通道与 **142 榀门架**（71×2）对账，缺站 0、插入 0。

冻结 deck `82548e6a` 的 `*INITIAL CONDITIONS, TYPE=STRESS` 是 ELSET+单轴。这不是 CalculiX 2.21 §7.76 合同。该文件未改写。

`41fb3222` 按 §7.76 写出 204 208 行合法八字段 PK2。CalculiX 2.21 读入成功，组装 879 076 方程，第一增量 SPOOLES 奇异。本岗独立复算其连通：**22096** 个使用节点分量、**19371** 个 2 节点碎片 = **17756** T3D2 + **1615** B31，与计算一致。**21426 是「分量里没有任何约束节点」**，不是 21426 个无约束节点。无约束节点是 **50676**（\(51896-1220\)）。三张锚并集 **1220**（312 ∪ 16 ∪ 904，面层∩门架 = 0）。`41fb3222` 作为奇异现场冻结，不改写。

新主 deck `c635dad7` 按该定义另写：图纸锚补段落到 \(x=-23.895/-44.909/4225.7\)；面层同纱缝合消耗 T3D2 碎片路径；B31 只走对缝；剩余无约束**分量**钉到 `N_ORPHAN_UNCONSTRAINED`；每个 T3D2 与 B31 写八字段 PK2（421 432 行）。独立回读后 1073 个分量、4 个无约束分量。CalculiX 2.21 在副本上读入成功，组装 **1 401 126** 方程，切线**可分解**（不再奇异），第一增量未收敛（exit 201，墙钟 63.65 s）。`.frd` 仍是 80 字节标题壳，无 DISP。本文不声称已求解。频率目标仍隔离。

**关键词：** 施工猫道；坐标过门；142 榀门架；面层/门架分锚；CalculiX 2.21；第二类 Piola–Kirchhoff；连通分量；无约束分量

## Abstract (English)

A millimetre centre-line STEP of the Zhangjinggao construction catwalk is mapped to \(x=\mathrm{chainage}-K16+876.000\). Floor-rope and portal-rope anchors are disjoint. Twenty-one passages and 142 portal frames (classifier U+6980, not U+698C) reconcile with zero insertions. Frozen deck `82548e6a` keeps its illegal ELSET+uniaxial `TYPE=STRESS` card. Site `41fb3222` is the IC-pass / first-increment-singular deck and is not rewritten. An independent reread of that site recovers 22 096 used-node components and 19 371 two-node fragments \(=\) 17 756 T3D2 \(+\) 1 615 B31. The integer 21 426 counts **components that contain no constrained node**, not unconstrained nodes (50 676). The three-card boundary union is 1 220. The new main deck `c635dad7` attaches drawing-anchor stubs, consumes T3D2 yarn gaps and B31 pairs, pins leftover unconstrained **components**, and writes 421 432 eight-field PK2 rows. CalculiX 2.21 reads it, assembles 1 401 126 equations, factors the tangent (not singular), and fails to converge the first increment. Four solver files exist without DISP. No spectrum is claimed.

---

## 1. 引言

### 1.1 相关工作

从 CAD 中心线到可求解有限元模型的自动管线，在房屋与桥梁中并不罕见，但它们通常继承已经对齐的坐标系和单一支承族。多跨悬索桥施工猫道打破这个假定：两幅走道、两族锚点桩号不同的承重索、离散门架、离散横通道，全部用公路桩号书写。仓库内理论包 `catwalk-theory/thirteen-mode-models` v1.2 已经冻结图纸拓扑和十四阶隔离协议；那是理论模型族，不是 CalculiX deck。先前 PR #18 交出了管线，但 `artifacts/` 为空。PR #19 先放下 `82548e6a`，再放下 `41fb3222`。本 run 不改这两张现场，另交新主哈希。

### 1.2 方法

本 run 执行 `catwalk-fem/SKILL.md` 与 `PLAN.md`。几何只来自已发布 STEP。材料、垂度、荷载来自图纸与复核报告。坐标过门是硬门：除非鞍点高程证据要求平移，否则恒等；禁止 `X-xmin`。拓扑按冻结图纸清单对账：21 道横通道，71×2=142 榀门架。锚分两族，不得并成一个混合集。`82548e6a` 与 `41fb3222` 冻结。新主 deck 由修补器+同一写入器另写到 `zjg_catwalk_main.inp`。ccx 只在副本上跑。读入成功、切线可分解、`.sta` 有增量行，都不等于已求解。已求解只承认：exit 0 且 `.frd` 含 DISP 且 `.sta` 有收敛增量。

### 1.3 实验

Release `catwalk-attachment23-v2.0-s10-20260716` 的中心线 STEP（139 991 条 TRIMMED_CURVE，`SI_UNIT(.MILLI.,.METRE.)`）换成米。恒等映射后 STEP 节点 \(X\in[0,4270.609]\) m，\(Z_{\max}=350.312\) m。三张哈希当场 `sha256sum` 与上表一致。CalculiX 2.21 官方二进制对 `c635dad7` 副本组装 1 401 126 方程后第一增量未收敛。

### 1.4 展望

新哈希已经交出，初应力词法已过，第一增量不再因 22096 个分量而立即奇异。下一步若要静力收敛，必须处理修补后仍在的 1073 个分量、477 个 2 节点碎片、4 个无约束分量，以及 `umpc_mean_rot` 失败，而不是改 `82548e6a` 或 `41fb3222`。没有已求解谱之前，不得打开 TARGET-FREQ。

---

## 2. 相关工作与隔离协议

### 2.1 相关工作

这里的 agentic FEA 指带冻结常数的可脚本、可审计链条，而不是对话里现场编截面。CalculiX 作为开源求解器，关键字 deck 可回读、版本可钉死。Abaqus 风格的「ELSET + 单轴预应力」是常见写作习惯，但不是 CalculiX 2.21 的合同。

### 2.2 方法

隔离规则取自理论 v1.2 §1 与 SKILL：

1. STEP 只提供坐标。
2. 属性只允许来自 DRW-A/B、CALC-INPUT、STD 或已登记 ASSUMP。
3. TARGET-FREQ 放在 `catwalk-fem/isolated/`，`write_inp` 与求解器 deck 不得导入。
4. 成型垂度 \(h=227.300\) m（\(340.600-113.300\)）。主缆控制垂度 255.56 m 禁止写入 deck（已核缺失）。
5. 两幅猫道独立自由度，禁止镜像约束。
6. 面层锚与门架锚不得求并。
7. SHA-256 `82548e6a` 与 `41fb3222` 冻结后，不得为了「让求解器高兴」改写这两份 `.inp`。

### 2.3 实验

隔离文件列出十四个频率，首项 0.0296 Hz。三份 deck 全文检索既无 `0.0296` 也无 `255.56`。`write_inp.py` 不导入 `isolated/TARGET-FREQ.json`。同 Release 的 `cw_S10_0716t050342_a4_eq.db` 写在禁止源清单里。

### 2.4 展望

隔离是科学主张，不是礼貌。以后任何对照表只能在 deck、求解和振型分类全部冻结后再加载 TARGET-FREQ。

---

## 3. 章程、证据等级与冻结常数

### 3.1 相关工作

证据等级沿用理论 v1.2：DRW-A/B、CALC-INPUT、STD、TEST、ASSUMP。门架与通道站位是 DRW-B 尺寸链。鞍点坐标是 CALC-INPUT（复核报告表 1-5 / 1-9）。

### 3.2 方法

章程（`artifacts/analysis_charter.json`）冻结：项目 `zjg-catwalk`，内部 SI 单位，四个工况 LC-DEAD-PRESTRESS、LC-PERSONNEL-UNIFORM、LC-WIND-Y、LC-FREQ。坐标原点是名义四跨北端，不是物理锚：

\[
x=\text{桩号}-K16+876.000,\quad
y\text{ 上游}\to\text{下游},\quad
z\text{ 向上}.
\]

四族物理锚分记：

\[
\begin{aligned}
x_{\text{floor,N}}&=-23.895~\text{m}\ (K16+852.105),&
x_{\text{floor,S}}&=4210.368~\text{m}\ (K21+086.368),\\
x_{\text{portal,N}}&=-44.909~\text{m}\ (K16+831.091),&
x_{\text{portal,S}}&=4225.700~\text{m}\ (K21+101.700).
\end{aligned}
\]

名义四跨端点 \(\{0,660,2960,3677,4180\}\) 与物理鞍点 \(\{666.679,2953.321\}\) 同时登记，不得静默混用。

### 3.3 实验

三份 deck 的 `*HEADING` 都用明文写出该公约。`82548e6a` / `41fb3222` 的 STEP 节点 \(x_{\min}=0\)。新主在图纸 stub 之后 \(x_{\min}=-44.909\)，STEP 导出节点仍从 0 起，未做 \(X-x_{\min}\)。

### 3.4 展望

以后若有覆盖北锚的 STEP，这四站仍必须保持四套集合。图纸 stub 是补段，不是把面层锚并进门架锚。

---

## 4. 翻模与分类（N02–N07）

### 4.1 相关工作

139 991 条中心线 TRIMMED_CURVE 不是构件角色模型。角色必须用几何对图纸格子恢复。

### 4.2 方法

`parse_step` 流式解析 `CARTESIAN_POINT` / `TRIMMED_CURVE`，核 STEP SHA-256，毫米改米。`classify_segments` 按图纸 \(y=\pm(21.45\pm(0.85+0.26k))\) 格子标面层索，长而高的标门架/扶手索，短横标 `portal_or_beam`，长跨幅标 `cross_passage`。

### 4.3 实验

原始计数：`floor_rope` 43 200，`portal_or_beam` 4 719，`portal_rope` 356，`cross_passage` 0，`short_other` 91 618。没有任何单段 \(\Delta y\ge 15\) m，因为每道约 49.655 m 的通道被切成约 1.7 m 的短段。在每个图纸通道 \(X\) 上，节点 \(Y\) 已经跨到 \([-24.3,24.3]\) m。因此用 Y 跨度识别，而不是一根长梁。未分类 `short_other` 不进粗化主 deck。纵向链保留图纸站，目标间距 12 m。

### 4.4 展望

粗化后门架索分类仍不完整。该有界项写在第 10 节，不靠 142 榀计数遮住。

---

## 5. 坐标系与拓扑过门（N07/N09）

### 5.1 相关工作

#18 的空 `artifacts/` 不能叫过门。拓扑计数必须用网格对图纸清单回读，缺站要记账，不得静默补杆充数却不写插入。

### 5.2 方法

`infer_x_transform` 对恒等、减 \(x_{\min}\)、减原始桩号三种变换打分。高程直方图峰在门架簇附近（约 700 m 与约 3023 m），不在鞍点。过门依据是鞍点邻域 \(Z_{p90}\)：在 \(x=666.679\) 与 \(x=2953.321\) 的 12 m 内。通道：21 个图纸站（3+13+3+2）。门架：71 站 × 2 幅 = **142 榀**。计数单位必须写「榀」（U+6980），不得写「榌」（U+698C）。

四跨门架尺寸链（理论 v1.2 §2.6，DRW-B）：

| 跨段 | 站数 | 尺寸链 | \(x\) 区间 |
|---|---:|---|---|
| 北边跨 660 m | 11 | \(45+10\times57+45=660\) | 45 … 615 |
| 主跨 2300 m | 41 | \(64+11\times57+18\times51+11\times57+64=2300\) | 724 … 2896 |
| 南侧 717 m | 11 | \(58.5+10\times60+58.5=717\) | 3018.5 … 3618.5 |
| 最南 503 m | 8 | \(52+7\times57+52=503\) | 3729 … 4128 |
| **单幅合计** | **71** | | |
| **两幅（榀）** | **142** | 上、下游各自独立 | |

### 5.3 实验

| 检查 | 结果 | 依据 |
|---|---|---|
| 单位 | PASS | mm STEP → m 节点；\(x_{\max}=4270.609<20\,000\) |
| 变换 | PASS | 恒等，shift \(=0\) |
| 鞍点 \(Z\) | PASS | 北 \(Z_{p90}=330.78\) m，南 324.85 m，对照 340.6 m |
| 两幅 | PASS | \(Y\) 中位数 \(+20.6\) / \(-20.6\) m，对照 \(\pm 21.45\) |
| 成型垂度 | PASS | 几何 214.18 m vs 227.30 m，\(\lvert\Delta\rvert=13.12\) m |
| `.inp` 未减 \(x_{\min}\) | PASS | STEP 节点 \(x_{\min}=0\)；图纸 stub 允许 \(x<0\) |
| 21 道横通道 | PASS | 21/21，插入 0 |
| 142 榀门架 | PASS | 上游 71 + 下游 71 = 142，缺 0，插入 0 |

21 道通道全部用 Y 跨度在 DRW-B 站上闭合（表 2）。142 榀门架逐站闭合（附录 A）：北 11、主 41、南 717 的 11、南 503 的 8，每站两幅都命中。

**表 2. 21 道横通道（DRW-B）**

| 序号 | 标签 | 跨段 | \(x\) (m) | 桩号 |
|---:|:---|:---|---:|:---|
| 1 | P01 | 北边跨 | 159 | K17+035.000 |
| 2 | P02 | 北边跨 | 330 | K17+206.000 |
| 3 | P03 | 北边跨 | 501 | K17+377.000 |
| 4 | P04 | 主跨 | 838 | K17+714.000 |
| 5 | P05 | 主跨 | 1009 | K17+885.000 |
| 6 | P06 | 主跨 | 1180 | K18+056.000 |
| 7 | P07 | 主跨 | 1351 | K18+227.000 |
| 8 | P08 | 主跨 | 1504 | K18+380.000 |
| 9 | P09 | 主跨 | 1657 | K18+533.000 |
| 10 | H1 | 主跨 | 1810 | K18+686.000 |
| 11 | H2 | 主跨 | 1963 | K18+839.000 |
| 12 | H3 | 主跨 | 2116 | K18+992.000 |
| 13 | H4 | 主跨 | 2269 | K19+145.000 |
| 14 | H5 | 主跨 | 2440 | K19+316.000 |
| 15 | H6 | 主跨 | 2611 | K19+487.000 |
| 16 | H7 | 主跨 | 2782 | K19+658.000 |
| 17 | H8 | 南 717 | 3138.5 | K20+014.500 |
| 18 | H9 | 南 717 | 3318.5 | K20+194.500 |
| 19 | H10 | 南 717 | 3498.5 | K20+374.500 |
| 20 | H11 | 南 503 | 3843 | K20+719.000 |
| 21 | H12 | 南 503 | 4014 | K20+890.000 |

### 5.4 展望

13.12 m 垂度残差落在 15 m 门内，但不是成型线拟合。后续 run 不得把直方图峰当作鞍点证据。

---

## 6. 材料、分族锚与索力初值（N08–N10）

### 6.1 相关工作

理论 v1.2 §4 禁止把面层索锚当成门架索锚。北端两族相差 21 m，南端相差 15.332 m。

### 6.2 方法

钢丝绳 \(E=1.20\times10^{11}\) Pa，面层/门架 \(A=1400.42\times10^{-6}\) m\(^2\)，\(\mu=12.038\) kg/m（CALC-INPUT / DRW-A）。钢材 \(E=2.06\times10^{11}\) Pa，\(\rho=7850\) kg/m\(^3\)。水平力初值

\[
H=\frac{wL^2}{8h},\quad h=227.300~\text{m},\quad L=2286.642~\text{m}.
\]

单幅 \(w_{\text{floor}}=2.766\) kN/m、\(w_{\text{portal}}=0.709\) kN/m，得 \(H_{\text{floor}}=7.954\) MN、\(H_{\text{portal}}=2.039\) MN。轴应力初值 \(\sigma_{\text{floor}}=3.549611\times10^{8}\) Pa、\(\sigma_{\text{portal}}=2.426295\times10^{8}\) Pa。L0 波动频率 \(f_1=\sqrt{g/32h}=0.036719\) Hz 只作量级门。

面层锚与门架锚用不同节点集、两张 `*BOUNDARY`。第三张卡是鞍点与名义端。新主另加第四张卡钉剩余无约束分量，不与前三张求并冒充锚。

### 6.3 实验

**表 3. 41fb3222 上的锚（STEP 端点代理，现场不改）**

| 族 | 桩号 | 目标 \(x\) | 选点 \(x_{\text{mean}}\) | 模式 |
|---|---|---:|---:|---|
| 面层北 | K16+852.105 | −23.895 | 0.000 | STEP 北端代理 |
| 面层南 | K21+086.368 | 4210.368 | 4209.985 | 匹配，\(\Delta=0.38\) m |
| 门架北 | K16+831.091 | −44.909 | 46.358 | STEP 北端代理 |
| 门架南 | K21+101.700 | 4225.700 | 4221.093 | 匹配，\(\Delta=4.61\) m |

**表 4. 新主 `c635dad7` 上的锚**

| 族 | 目标 \(x\) | 选点 \(x_{\text{mean}}\) | 模式 |
|---|---:|---:|---|
| 面层北 | −23.895 | −23.895 | 图纸 \(x\) stub，12 点 |
| 面层南 | 4210.368 | 4209.985 | 匹配，\(\Delta=0.38\) m |
| 门架北 | −44.909 | −44.909 | 图纸 \(x\) stub，12 点 |
| 门架南 | 4225.700 | 4225.700 | 图纸 \(x\) stub，4 点 |

两份 deck 上 `N_FLOOR_ANCHOR` 312 与 `N_PORTAL_ANCHOR` 16 交集均为空。

### 6.4 展望

stub 把图纸负 \(x\) 写进新主，不回写 41fb3222。南面层仍是匹配，不是 stub。

---

## 7. 计算工况（N11）

### 7.1 相关工作

CalculiX 不在步间继承 `*DLOAD`/`*CLOAD`。每一步必须重写重力与当前荷载包。

### 7.2 方法

复核报告的单幅包按 16 根显式面层索均分，使 \(\sum_i w_{\text{rope}}L_i=w_{\text{deck}}L_{\text{deck}}\)。

### 7.3 实验

| 工况 | 单幅 \(w\) | 单索 \(w\) | 合力（新主回读） |
|---|---:|---:|---:|
| 二期恒载（扣索自重后） | 877.16 N/m | 54.82 N/m | 10.756 MN |
| 人群 | 8.400 kN/m | 525 N/m | 103.006 MN |
| 风 \(+Y\) | 0.50 kN/m | 31.25 N/m | 6.131 MN |

新主面层桁架总长 196 202 m（含同纱缝合后的加长）。LC-FREQ 求 20 个特征值，正文不含 0.0296 Hz。

### 7.4 展望

面层总长偏长是分类与缝合有界项，不是活载发明。21/142 对账闭合后这项仍然要写出来。

---

## 8. 41fb3222 连通定义表（本岗独立复算）

### 8.1 相关工作

上一轮把 `41fb3222` 写成「新主 deck」，并把切线奇异归因于「22 096 个不连通分量」。分量个数成立，但 21426 曾被容易读成无约束节点数。用户更正：21426 是无约束**分量**。

### 8.2 方法

`pipeline/singular_audit.py` 只读 `zjg_catwalk_ccx221.inp`。连通在使用节点的单元邻接图上算。约束节点取三张 `*BOUNDARY` 卡的并集：`N_FLOOR_ANCHOR` ∪ `N_PORTAL_ANCHOR` ∪ `N_SUPPORT_SADDLE_ENDS`。一个分量若其节点与该并集交集为空，记为无约束分量。2 节点碎片按单元类型拆成 T3D2 / B31。不改写该文件。

### 8.3 实验

当场 `sha256sum` = `41fb3222…bbca924a`。`test_singular_defs` 通过。`match_given.all = true`。

**表 5. 41fb3222 定义表（本岗复算 = 计算）**

| 量 | 值 | 含义 |
|---|---:|---|
| 使用节点连通分量 | **22096** | used-node connected components |
| 2 节点碎片 | **19371** | size-2 components |
| 其中 T3D2 | **17756** | floor_rope 17616 + portal_rope 136 + handrail_rope 4 |
| 其中 B31 | **1615** | portal_or_beam 1594 + cross_passage 21 |
| 无约束**分量** | **21426** | 分量里**没有任何**约束节点。不是无约束节点个数 |
| 无约束**节点** | **50676** | \(51896-1220\) |
| 三张锚并集 | **1220** | 312 ∪ 16 ∪ 904；面层∩门架 = 0 |
| 节点 / 单元 | 51896 / 30317 | |

恒等式：\(19371=17756+1615\)，\(50676=51896-1220\)，\(21426\neq50676\)。

41fb3222 上的 ccx 2.21：IC 读入成功，879 076 方程，SPOOLES `matrix found to be singular`，exit 255，墙钟 10.35 s。`.frd` 80 B，无 DISP；`.sta`/`.cvg` 无增量行。不是解。

有界项（现场保留，不改哈希）：T3D2 写了 8 积分点（C3D8I 展开，IC 被接受）；北面层锚 \(x=0\) vs −23.895；北门架 \(x\approx43.9\)–48.8 vs −44.909；南门架 4221.093 vs 4225.7；B31 与其余 51 个 T3D2 无 IC。

### 8.4 展望

定义表是新主修补的输入，不是把 41fb3222 判成未交。禁止把 21426 当成节点数去钉 21426 个点。

---

## 9. 新主 deck `c635dad7` 与 CalculiX 2.21

### 9.1 相关工作

CalculiX CrunchiX 2.21 用户手册 §6.11.7 与 §7.76 规定：`*INITIAL CONDITIONS, TYPE=STRESS` 必须出现在第一个 `*STEP` 之前。未给 `USER` 时，每行数据为单元号、积分点号、\(S_{xx}~S_{yy}~S_{zz}~S_{xy}~S_{xz}~S_{yz}\)，在**全局**直角坐标下以**第二类 Piola–Kirchhoff** 应力给出。T3D2 按 §6.2.35 随 B31 扩成 C3D8I，积分点按 2×2×2 共 8 个写出。Abaqus 式「ELSET + 单轴」不是这份合同。

### 9.2 方法

`repair_topology.py` 从 41fb3222 **只读**回读网格，不写回该路径：

1. 图纸锚 stub：28 根，落到 −23.895 / −44.909 / 4225.7。
2. 面层同纱缝合：同角色+同侧+同 \(Y\)（三位小数）按 \(X\) 相邻，\(\Delta x\le 15\) m 加 T3D2。20948 根。这是 17756 条 T3D2 碎片路径，不是 57–2000 m 门架/扶手缝。
3. B31 对缝：同侧，\(\lvert\Delta x\rvert\le 4\) m，\(d\le 3.5\) m。485 根。只走 1615 条 B31 碎片。
4. 漂浮 `portal_or_beam` / `cross_passage` / `portal_rope` 耦到最近面层节点：724 + 21 + 156。
5. 剩余无约束**分量**（修补后仍到不了族锚或鞍点）写入 `N_ORPHAN_UNCONSTRAINED`：1012 个分量 / 3596 节点。

`write_inp.py` 对**每一个** T3D2 与 B31 写八字段 PK2。面层/门架索 \(S=\sigma n\otimes n\)，八个积分点重复；其余角色零 PK2。发射脚本 `emit_bound_main_deck.py` 拒绝改 82548e6a / 41fb3222。`emit_new_main_deck.py` 现拒绝覆盖 41fb3222。

### 9.3 实验

独立回读（`eval/bound_main_reread.json`，`eval/SINGULAR_DEFS_c635dad7.json`）：

| 项 | 值 |
|---|---|
| SHA-256 | `c635dad7…70cda84` |
| 字节 | 47 948 333 |
| 节点 / 单元 | 51924 / 52679 |
| IC 行数 | 421 432（floor 370072 + portal 3192 + 其他 T3D2 408 + B31 47760） |
| 合法八字段 | 421 432 |
| ELSET+单轴 | 0 |
| 首行 | `1, 1, 1.439957e+08, 0, 2.109655e+08, 0, 1.742932e+08, 0` |
| \(\mathrm{tr}(S)\) 首样 | \(= \sigma_{\mathrm{floor}}\) |
| 连通分量 | 1073 |
| 剩余 2 节点碎片 | 477 = 110 T3D2 + 367 B31 |
| 无约束分量（全约束卡） | 4 |
| 三张锚并集 | 1232 |
| 三张卡下无约束节点 | 50692 |
| 自动门 | 29/29 PASS |

CalculiX 2.21（官方 ELF + libgfortran4）在 `/tmp/ccx-c635dad7` 副本上：

```
This is Version 2.21
copy_sha256 = c635dad7…70cda84
frozen_82548e6a_untouched = true
site_41fb3222_untouched = true
parse_fail_ic = false
number of equations = 1401126
singular = false
exit 201
wall_s = 63.65
has_disp = false
n_sta_increment_rows = 1
solved = false
```

**表 6. 三张哈希的求解器四件套**

| 哈希 | 方程 | 奇异 | 增量行 | DISP | exit | 墙钟 (s) |
|---|---:|:---:|---:|:---:|---:|---:|
| 82548e6a | — | — | 0 | 无 | 201 | <1 |
| 41fb3222 | 879 076 | 是 | 0 | 无 | 255 | 10.35 |
| c635dad7 | 1 401 126 | 否 | 1（`1U`） | 无 | 201 | 63.65 |

`c635dad7` 的 `.sta`：`1 1 1U 2`（未收敛）。`.cvg` 四行迭代，残差 \(10^7\)–\(10^8\) %，位移修正 100%。stdout：`no convergence` / `divergence` / `*ERROR in umpc_mean_rot`（节点 78746）。`.frd` 80 B 标题。不是解。

求解后再核：82548e6a 与 41fb3222 哈希未变。

### 9.4 展望

初应力词法门与「第一增量不再立即奇异」已经覆盖。下一步是收敛，不是再改 §7.76 行格式，也不是改两张冻结现场。

---

## 10. 讨论与结论

### 10.1 相关工作

PR #18 交出空目录。PR #19 先放下 `82548e6a`，再放下 `41fb3222`。本 run 按已给定义表另交 `c635dad7`，并留下 eval 痕迹。

### 10.2 方法

看得见的有界项写成 bounds。硬门（恒等变换、21/142 榀、锚分集、§7.76 词法、两张冻结哈希未改、禁源、21426 定义）闭合。第一增量未收敛是有界项，不是把新 deck 判成未交。

### 10.3 实验（有界项，不粉饰）

- 41fb3222 北锚是 STEP 端点代理。新主用图纸 stub 补了北面层/北门架/南门架；南面层仍 \(\Delta=0.38\) m。
- 门架索分类不完整；142 榀是站位，不是索单元数。
- 几何垂度 214.18 m 对 227.30 m，过 15 m 门，不是成型线拟合。
- 面层索总长偏长。
- 修补后仍有 1073 个分量、477 个 2 节点碎片、4 个无约束分量。
- orphan 钉是分量诊断剩余项，不是把碎片焊成一张静定网。
- 新哈希切线可分解，第一增量未收敛，无 DISP。
- 四件套有文件，没有完成增量。
- TARGET-FREQ 未打开。没有十四阶复现。

### 10.4 结论

> 从已发布 STEP 出发，在 \(x=\text{桩号}-K16+876.000\) 下可以生成可回读的 CalculiX deck；面层锚与门架锚分开；21 道横通道与 **142 榀门架**对账闭合且插入为 0。冻结哈希 `82548e6a` 的 `TYPE=STRESS` 为 ELSET+单轴，未改。`41fb3222` 按 §7.76 写出八字段 PK2，读入过门后因连通奇异；本岗复算 22096 分量、19371=17756+1615 个 2 节点碎片、**21426 个无约束分量**、50676 个无约束节点、1220 三张锚并集，与计算一致；该哈希不动。新主 `c635dad7` 按该定义另写（图纸锚、T3D2 同纱缝、B31 对缝、无约束分量钉、全单元八字段 PK2）。CalculiX 2.21 读入成功并组装 1 401 126 方程，切线可分解，第一增量未收敛。不是已求解谱，不是十四阶复现。

不支持的主张：已求解位移、十四阶同序复现、41fb3222 北锚已落到物理桩号、中心线已连成一张静定/超静定网、21426 是无约束节点个数。

---

## 复现

```bash
python3 catwalk-fem/tests/test_coord_gate.py
python3 catwalk-fem/tests/test_write_inp.py
python3 catwalk-fem/tests/test_reconcile.py
python3 catwalk-fem/tests/test_audit_frozen_deck.py
python3 catwalk-fem/tests/test_new_main_deck.py
python3 catwalk-fem/tests/test_singular_defs.py
python3 catwalk-fem/tests/test_repair_topology.py
python3 catwalk-fem/pipeline/singular_audit.py catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
python3 catwalk-fem/pipeline/emit_bound_main_deck.py
sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
sha256sum catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
sha256sum catwalk-fem/artifacts/zjg_catwalk_main.inp
cd catwalk-fem/paper && pdflatex -interaction=nonstopmode zjg_catwalk_agentic_fea.tex
```

不要把 77 MB STEP 入库。不要把 `isolated/TARGET-FREQ.json` 喂给写入器或求解器。不要改写 `zjg_catwalk_coarsened.inp`。不要改写 `zjg_catwalk_ccx221.inp`。不要 push（本 run 约束）。

## 数据

分支 `cursor/catwalk-main-deck-bound-4c2c`。冻结 `82548e6a…276ab6da`。奇异现场 `41fb3222…bbca924a`。新主 `c635dad7…70cda84`。自评 `catwalk-fem/eval/GROK_SELF_EVAL.md`。定义表 `eval/DEFINITION_TABLE_41fb3222.md`。142 榀表 `artifacts/portal_142_table.md`（榀，不是榌）。

## 参考文献

1. G. Dhondt, *CalculiX CrunchiX USER'S MANUAL version 2.21*, 2023, §6.2.35, §7.76。
2. 张靖皋猫道十四项低阶模态独立理论建模与理论验证 v1.2，`catwalk-theory/thirteen-mode-models`。
3. `catwalk-fem/SKILL.md`，`catwalk-fem/PLAN.md`。
4. Release `catwalk-attachment23-v2.0-s10-20260716`，`cw_S10_0716t050342_a4_centerline.step`，SHA-256 `d03d01e3…763344`。
5. 冻结现场：ccx 对 `82548e6a` 读入失败（`E_FLOOR_ROPE,3.549611E+08`，exit 201）。
6. 奇异现场：`eval/ccx_41fb3222/`，879 076 方程，矩阵奇异。
7. 新主求解：`eval/ccx_c635dad7/`，1 401 126 方程，切线可分解，第一增量未收敛。

---

## 附录 A　142 榀门架逐站对账（不是榌）

单幅 71 站 × 两幅 = **142 榀**。缺站 0，插入 0。完整表见 `artifacts/portal_142_table.md`，由 `portal_142_ledger.json` 生成。下面按跨段汇总后再列全表。

**跨段汇总**

| 跨段 | 图纸站 | 上游命中 | 下游命中 | 榀 |
|---|---:|---:|---:|---:|
| 北边跨 660 m | 11 | 11 | 11 | 22 |
| 主跨 2300 m | 41 | 41 | 41 | 82 |
| 南侧 717 m | 11 | 11 | 11 | 22 |
| 最南 503 m | 8 | 8 | 8 | 16 |
| 合计 | 71 | 71 | 71 | **142** |

**逐站全表（上游+下游都命中才算该站 2 榀）**

| 序号 | \(x\) (m) | 桩号 | 跨段 | 上游 | 下游 | n_up | n_dn | ok |
|---:|---:|:---|:---|:---:|:---:|---:|---:|:---:|
| 1 | 45.0 | K16+921.000 | north_660 | Y | Y | 5 | 5 | Y |
| 2 | 102.0 | K16+978.000 | north_660 | Y | Y | 8 | 8 | Y |
| 3 | 159.0 | K17+035.000 | north_660 | Y | Y | 8 | 8 | Y |
| 4 | 216.0 | K17+092.000 | north_660 | Y | Y | 31 | 35 | Y |
| 5 | 273.0 | K17+149.000 | north_660 | Y | Y | 8 | 8 | Y |
| 6 | 330.0 | K17+206.000 | north_660 | Y | Y | 8 | 8 | Y |
| 7 | 387.0 | K17+263.000 | north_660 | Y | Y | 32 | 35 | Y |
| 8 | 444.0 | K17+320.000 | north_660 | Y | Y | 9 | 9 | Y |
| 9 | 501.0 | K17+377.000 | north_660 | Y | Y | 8 | 8 | Y |
| 10 | 558.0 | K17+434.000 | north_660 | Y | Y | 34 | 38 | Y |
| 11 | 615.0 | K17+491.000 | north_660 | Y | Y | 9 | 9 | Y |
| 12 | 724.0 | K17+600.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 13 | 781.0 | K17+657.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 14 | 838.0 | K17+714.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 15 | 895.0 | K17+771.000 | main_2300 | Y | Y | 24 | 29 | Y |
| 16 | 952.0 | K17+828.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 17 | 1009.0 | K17+885.000 | main_2300 | Y | Y | 9 | 9 | Y |
| 18 | 1066.0 | K17+942.000 | main_2300 | Y | Y | 25 | 30 | Y |
| 19 | 1123.0 | K17+999.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 20 | 1180.0 | K18+056.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 21 | 1237.0 | K18+113.000 | main_2300 | Y | Y | 25 | 26 | Y |
| 22 | 1294.0 | K18+170.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 23 | 1351.0 | K18+227.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 24 | 1402.0 | K18+278.000 | main_2300 | Y | Y | 45 | 50 | Y |
| 25 | 1453.0 | K18+329.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 26 | 1504.0 | K18+380.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 27 | 1555.0 | K18+431.000 | main_2300 | Y | Y | 45 | 50 | Y |
| 28 | 1606.0 | K18+482.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 29 | 1657.0 | K18+533.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 30 | 1708.0 | K18+584.000 | main_2300 | Y | Y | 44 | 49 | Y |
| 31 | 1759.0 | K18+635.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 32 | 1810.0 | K18+686.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 33 | 1861.0 | K18+737.000 | main_2300 | Y | Y | 45 | 50 | Y |
| 34 | 1912.0 | K18+788.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 35 | 1963.0 | K18+839.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 36 | 2014.0 | K18+890.000 | main_2300 | Y | Y | 45 | 50 | Y |
| 37 | 2065.0 | K18+941.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 38 | 2116.0 | K18+992.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 39 | 2167.0 | K19+043.000 | main_2300 | Y | Y | 45 | 50 | Y |
| 40 | 2218.0 | K19+094.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 41 | 2269.0 | K19+145.000 | main_2300 | Y | Y | 10 | 10 | Y |
| 42 | 2326.0 | K19+202.000 | main_2300 | Y | Y | 29 | 32 | Y |
| 43 | 2383.0 | K19+259.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 44 | 2440.0 | K19+316.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 45 | 2497.0 | K19+373.000 | main_2300 | Y | Y | 30 | 33 | Y |
| 46 | 2554.0 | K19+430.000 | main_2300 | Y | Y | 9 | 9 | Y |
| 47 | 2611.0 | K19+487.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 48 | 2668.0 | K19+544.000 | main_2300 | Y | Y | 32 | 37 | Y |
| 49 | 2725.0 | K19+601.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 50 | 2782.0 | K19+658.000 | main_2300 | Y | Y | 9 | 9 | Y |
| 51 | 2839.0 | K19+715.000 | main_2300 | Y | Y | 32 | 37 | Y |
| 52 | 2896.0 | K19+772.000 | main_2300 | Y | Y | 8 | 8 | Y |
| 53 | 3018.5 | K19+894.500 | south_717 | Y | Y | 8 | 8 | Y |
| 54 | 3078.5 | K19+954.500 | south_717 | Y | Y | 9 | 9 | Y |
| 55 | 3138.5 | K20+014.500 | south_717 | Y | Y | 8 | 8 | Y |
| 56 | 3198.5 | K20+074.500 | south_717 | Y | Y | 8 | 8 | Y |
| 57 | 3258.5 | K20+134.500 | south_717 | Y | Y | 8 | 8 | Y |
| 58 | 3318.5 | K20+194.500 | south_717 | Y | Y | 8 | 8 | Y |
| 59 | 3378.5 | K20+254.500 | south_717 | Y | Y | 9 | 9 | Y |
| 60 | 3438.5 | K20+314.500 | south_717 | Y | Y | 8 | 8 | Y |
| 61 | 3498.5 | K20+374.500 | south_717 | Y | Y | 9 | 9 | Y |
| 62 | 3558.5 | K20+434.500 | south_717 | Y | Y | 8 | 8 | Y |
| 63 | 3618.5 | K20+494.500 | south_717 | Y | Y | 8 | 8 | Y |
| 64 | 3729.0 | K20+605.000 | south_503 | Y | Y | 8 | 8 | Y |
| 65 | 3786.0 | K20+662.000 | south_503 | Y | Y | 8 | 8 | Y |
| 66 | 3843.0 | K20+719.000 | south_503 | Y | Y | 8 | 8 | Y |
| 67 | 3900.0 | K20+776.000 | south_503 | Y | Y | 23 | 24 | Y |
| 68 | 3957.0 | K20+833.000 | south_503 | Y | Y | 8 | 8 | Y |
| 69 | 4014.0 | K20+890.000 | south_503 | Y | Y | 8 | 8 | Y |
| 70 | 4071.0 | K20+947.000 | south_503 | Y | Y | 22 | 24 | Y |
| 71 | 4128.0 | K21+004.000 | south_503 | Y | Y | 8 | 8 | Y |

71 站全部 `ok=Y`，上、下游都命中，故 \(71\times2=142\) 榀，插入 0。

## 附录 B　CalculiX 2.21 摘录

**B.1 冻结哈希 `82548e6a`（未改）**

```
*ERROR reading *INITIAL CONDITIONS. Card image:
       E_FLOOR_ROPE,3.549611E+08
*ERROR in calinput: at least one fatal
       error message while reading the
       input deck: CalculiX stops.
```

无 `.frd`。哈希未改。

**B.2 奇异现场 `41fb3222`（未改）**

```
number of equations
 879076
Factoring the system of equations using the symmetric spooles solver
```

`spooles.out`：`matrix found to be singular`。四件套：`.frd` 80 B，`.dat` 42 B，`.sta` 98 B，`.cvg` 274 B。exit 255。墙钟 10.35 s。`parse_fail_ic=false`。

**B.3 新主 `c635dad7`**

```
number of equations
 1401126
number of nonzero lower triangular matrix elements
 22675650
Factoring the system of equations using the symmetric spooles solver
...
no convergence
divergence; the increment size is decreased to 1.250000e-02
*ERROR in umpc_mean_rot
       no mean rotation MPC can be
       generated for the MPC containing
       node        78746
```

`.frd` 80 B，无 DISP。`.sta` 一行 `1U`。`.cvg` 四行迭代。exit 201。墙钟 63.65 s。`singular=false`。不是已求解。

**B.4 新 deck 初应力首行（独立回读）**

```
*INITIAL CONDITIONS, TYPE=STRESS
1, 1, 1.439957e+08, 0.000000e+00, 2.109655e+08, 0.000000e+00, 1.742932e+08, 0.000000e+00
```

其后积分点 2–8 重复。共 421 432 行。每个 T3D2 与每个 B31 都写了。
