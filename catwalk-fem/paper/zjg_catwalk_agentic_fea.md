# 张靖皋施工猫道的 Agentic 有限元翻模

**坐标过门、142 榀门架对账，以及冻结哈希上 CalculiX 2.21 的初应力词法失败**

Run `catwalk-main-deck-gate-f23d`。仓库 `Hiram-test/model`，分支 `cursor/catwalk-main-deck-gate-f23d`，PR #19。  
几何：Release `catwalk-attachment23-v2.0-s10-20260716`  
`cw_S10_0716t050342_a4_centerline.step` SHA-256 `d03d01e38b823df5af4c1ff9b0b175fdfb87b097b9cda9a03af5d14e9c763344`。  
主 deck SHA-256 `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da`（7 702 117 字节）。**不改该哈希。**  
门架计数单位是「榀」，不是「槬」。26/26 坐标门 PASS。CalculiX 2.21 已在该哈希的副本上执行，exit 201。

## 摘要

本文记录张靖皋施工猫道一次可审计的端到端 agentic 有限元翻模。77 MB 毫米制中心线 STEP 被解析后，映射到约定 \(x=\text{桩号}-K16+876.000\)，按图纸拓扑分类、粗化，并写成完整 CalculiX `.inp`。面层承重索锚与门架承重索锚分属不同 `*NSET` / `*BOUNDARY`，交集为空。21 道横通道与 142 榀门架（单幅 71 站 × 两幅）按图纸站表对账，缺站 0、插入 0。冻结主 deck 为 `catwalk-fem/artifacts/zjg_catwalk_coarsened.inp`，SHA-256 `82548e6a…276ab6da`，本文不改写该文件。

已给计算：ccx 已对 `82548e6a` 跑过，哈希未改；读入 `*INITIAL CONDITIONS` 失败（`E_FLOOR_ROPE,3.549611E+08`，exit 201）；无 `.frd`，`.dat` 空，`.sta`/`.cvg` 只有表头；墙钟 <1 s，无方程数。本机用 CalculiX 2.21 在字节相同的副本上复现：exit 201，墙钟 0.74–0.82 s，stdout 写明 `*ERROR reading *INITIAL CONDITIONS. Card image: E_FLOOR_ROPE,3.549611E+08`。这份 deck 的 `TYPE=STRESS` 是 ELSET+单轴；ccx 2.21 §7.76 要单元号+积分点+六应力。频率目标仍隔离。本文签发的是「带哈希、坐标过门、拓扑对账的 deck」加上「已记录的求解器词法失败」，不是已求解谱，不是十四阶复现。

**关键词：** 施工猫道；坐标过门；142 榀门架；面层/门架分锚；CalculiX 2.21；`*INITIAL CONDITIONS, TYPE=STRESS`

## Abstract (English)

A millimetre centre-line STEP of the Zhangjinggao construction catwalk is mapped to \(x=\mathrm{chainage}-K16+876.000\), classified against drawing topology, and written as a CalculiX deck. Floor-rope and portal-rope anchors are disjoint. Twenty-one passages and 142 portal frames reconcile with zero insertions. The frozen SHA-256 is `82548e6a…276ab6da` and is not rewritten. CalculiX 2.21 fails while reading `*INITIAL CONDITIONS` on `E_FLOOR_ROPE,3.549611E+08` (exit 201): no `.frd`, empty `.dat`, header-only `.sta`/`.cvg`, wall-clock \(<1\) s, no assembled equation count. The card is ELSET plus uniaxial stress; CalculiX 2.21 requires element number, integration point, and six stresses. Twenty-six gates PASS. No spectrum is claimed.

---

## 1. 引言

### 1.1 相关工作

从 CAD 中心线到可求解有限元模型的自动管线，在房屋与桥梁中并不罕见，但它们通常继承已经对齐的坐标系和单一支承族。多跨悬索桥施工猫道打破这个假定：两幅走道、两族锚点桩号不同的承重索、离散门架、离散横通道，全部用公路桩号书写。仓库内理论包 `catwalk-theory/thirteen-mode-models` v1.2 已经冻结图纸拓扑和十四阶隔离协议；那是理论模型族，不是 CalculiX deck。先前 PR #18 交出了管线，但 `artifacts/` 为空，空目录不能叫过门。

### 1.2 方法

本 run 执行 `catwalk-fem/SKILL.md` 与 `PLAN.md`。几何只来自已发布 STEP。材料、垂度、荷载来自图纸与复核报告。坐标过门是硬门：除非鞍点高程证据要求平移，否则恒等；禁止 `X-xmin`。拓扑按冻结图纸清单对账：21 道横通道，71×2=142 榀门架。锚分两族，不得并成一个混合集。写出完整关键字 deck 后冻结哈希；此后只允许在副本上跑 ccx。

### 1.3 实验

Release `catwalk-attachment23-v2.0-s10-20260716` 的中心线 STEP（139 991 条 TRIMMED_CURVE，`SI_UNIT(.MILLI.,.METRE.)`）换成米。恒等映射后 \(X\in[0,4270.609]\) m，\(Z_{\max}=350.312\) m。写出 deck：51 896 节点、30 317 单元、7 702 117 字节。CalculiX 2.21 在哈希 `82548e6a` 的副本上于读入第一行初应力时失败。

### 1.4 展望

以后若要让求解器读过初应力，必须另写新哈希 deck，而不是改 `82548e6a`。北侧物理锚在本 STEP 之外，仍是端点代理。没有已求解谱之前，不得打开 TARGET-FREQ 做十四阶对照。

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
7. SHA-256 `82548e6a` 冻结后，不得为了「让求解器高兴」改写 `.inp`。

### 2.3 实验

隔离文件列出十四个频率，首项 0.0296 Hz。冻结 deck 全文检索既无 `0.0296` 也无 `255.56`。`write_inp.py` 不导入 `isolated/TARGET-FREQ.json`。同 Release 的 `cw_S10_0716t050342_a4_eq.db` 写在禁止源清单里。

### 2.4 展望

隔离是科学主张，不是礼貌。以后任何对照表只能在 deck、求解和振型分类全部冻结后再加载 TARGET-FREQ。

---

## 3. 章程、证据等级与冻结常数

### 3.1 相关工作

证据等级沿用理论 v1.2：DRW-A/B、CALC-INPUT、STD、TEST、ASSUMP。门架与通道站位是 DRW-B 尺寸链。鞍点坐标是 CALC-INPUT（复核报告表 1-5 / 1-9）。

### 3.2 方法

章程（`artifacts/analysis_charter.json`）冻结：项目 `zjg-catwalk`，run `catwalk-main-deck-gate-f23d`，内部 SI 单位，四个工况 LC-DEAD-PRESTRESS、LC-PERSONNEL-UNIFORM、LC-WIND-Y、LC-FREQ。坐标原点是名义四跨北端，不是物理锚：

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

冻结 deck 的 `*HEADING` 用明文写出该公约。节点 \(x_{\min}=0\) 等于变换后几何 \(x_{\min}\)。南面层与南门架选点均值相差 11.1 m。

### 3.4 展望

以后若有覆盖北锚的 STEP，这四站仍必须保持四套集合。

---

## 4. 翻模与分类（N02–N07）

### 4.1 相关工作

139 991 条中心线 TRIMMED_CURVE 不是构件角色模型。角色必须用几何对图纸格子恢复。

### 4.2 方法

`parse_step` 流式解析 `CARTESIAN_POINT` / `TRIMMED_CURVE`，核 STEP SHA-256，毫米改米。`classify_segments` 按图纸 \(y=\pm(21.45\pm(0.85+0.26k))\) 格子标面层索，长而高的标门架/扶手索，短横标 `portal_or_beam`，长跨幅标 `cross_passage`。

### 4.3 实验

原始计数：`floor_rope` 43 200，`portal_or_beam` 4 719，`portal_rope` 356，`cross_passage` 0，`short_other` 91 618。没有任何单段 \(\Delta y\ge 15\) m，因为每道约 49.655 m 的通道被切成约 1.7 m 的短段。在每个图纸通道 \(X\) 上，节点 \(Y\) 已经跨到 \([-24.3,24.3]\) m。因此用 Y 跨度识别，而不是一根长梁。未分类 `short_other` 不进粗化主 deck。纵向链保留图纸站，目标间距 12 m。

### 4.4 展望

粗化后门架索分类仍不完整（227 个单元）。该有界项写在第 9 节，不靠 142 榀计数遮住。

---

## 5. 坐标系与拓扑过门（N07/N09）

### 5.1 相关工作

#18 的空 `artifacts/` 不能叫过门。拓扑计数必须用网格对图纸清单回读，缺站要记账，不得静默补杆充数却不写插入。

### 5.2 方法

`infer_x_transform` 对恒等、减 \(x_{\min}\)、减原始桩号三种变换打分。高程直方图峰在门架簇附近（约 700 m 与约 3023 m），不在鞍点。过门依据是鞍点邻域 \(Z_{p90}\)：在 \(x=666.679\) 与 \(x=2953.321\) 的 12 m 内。通道：21 个图纸站（3+13+3+2）。门架：71 站 × 2 幅 = **142 榀**。计数单位必须写「榀」（U+6980），不得写「槬」（U+69EC）。

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
| `.inp` 未减 \(x_{\min}\) | PASS | 节点 \(x_{\min}=0\) 等于几何 |
| 21 道横通道 | PASS | 21/21，插入 0 |
| 142 榀门架 | PASS | 上游 71 + 下游 71 = 142，缺 0，插入 0 |

21 道通道全部用 Y 跨度在 DRW-B 站上闭合（表 2）。142 榀门架逐站闭合（附录 A / `portal_142_table.md`）：北 11、主 41、南 717 的 11、南 503 的 8，每站两幅都命中。

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

面层锚与门架锚用不同节点集、两张 `*BOUNDARY`。第三张卡是鞍点与名义端。

### 6.3 实验

| 族 | 桩号 | 目标 \(x\) | 选点 \(x_{\text{mean}}\) | 模式 |
|---|---|---:|---:|---|
| 面层北 | K16+852.105 | −23.895 | 0.000 | STEP 北端代理 |
| 面层南 | K21+086.368 | 4210.368 | 4209.985 | 匹配，\(\Delta=0.38\) m |
| 门架北 | K16+831.091 | −44.909 | 46.358 | STEP 北端代理 |
| 门架南 | K21+101.700 | 4225.700 | 4221.093 | 匹配，\(\Delta=4.61\) m |

`N_FLOOR_ANCHOR` 312 个节点与 `N_PORTAL_ANCHOR` 16 个节点交集为空。`*BOUNDARY` 三张卡：`N_FLOOR_ANCHOR` / `N_PORTAL_ANCHOR` / `N_SUPPORT_SADDLE_ENDS`。南侧两族在 \(x\) 上仍差 11.1 m。

### 6.4 展望

deck 不在负 \(x\) 造点。以后若 STEP 覆盖北锚碇，四族仍须分开。

---

## 7. 计算工况（N11）

### 7.1 相关工作

CalculiX 不在步间继承 `*DLOAD`/`*CLOAD`。每一步必须重写重力与当前荷载包。

### 7.2 方法

复核报告的单幅包按 16 根显式面层索均分，使 \(\sum_i w_{\text{rope}}L_i=w_{\text{deck}}L_{\text{deck}}\)。

### 7.3 实验

| 工况 | 单幅 \(w\) | 单索 \(w\) | 合力 | 闭合 |
|---|---:|---:|---:|---|
| 二期恒载（扣索自重后） | 877.16 N/m | 54.82 N/m | 9.019 MN | 对 \(wL\) 精确 |
| 人群 | 8.400 kN/m | 525 N/m | 86.371 MN | 精确 |
| 风 \(+Y\) | 0.50 kN/m | 31.25 N/m | 5.141 MN | 精确 |

粗化后地面层桁架总长 164 516 m（32 条线，含垂度与误标面层的残差；约 5141 m/根，对照约 4300 m）。LC-FREQ 求 20 个特征值，正文不含 0.0296 Hz。

### 7.4 展望

面层总长偏长约 20% 是分类有界项，不是活载发明。21/142 对账闭合后这项仍然要写出来。

---

## 8. 求解器 deck 与 CalculiX 2.21 初应力门（N12–N14）

### 8.1 相关工作

CalculiX CrunchiX 2.21 用户手册 §6.11.7 与 §7.76 规定：`*INITIAL CONDITIONS, TYPE=STRESS` 必须出现在第一个 `*STEP` 之前。未给 `USER` 时，每行数据为

> 单元号，积分点号，\(S_{xx}\)，\(S_{yy}\)，\(S_{zz}\)，\(S_{xy}\)，\(S_{xz}\)，\(S_{yz}\)

在全局直角坐标下，以第二类 Piola–Kirchhoff 应力给出。Abaqus 式「ELSET + 单轴应力」不是这份合同。

### 8.2 方法

当前写入器写出（冻结 deck 第 90863–90865 行）：

```
*INITIAL CONDITIONS, TYPE=STRESS
E_FLOOR_ROPE, 3.549611e+08
E_PORTAL_ROPE, 2.426295e+08
```

这是 ELSET+单轴。哈希 `82548e6a` 已冻结，不打补丁。ccx 只在 `/tmp/ccx-82548e6a/` 的副本上运行。原文件在运行前后重新哈希。

词法审计脚本 `pipeline/audit_frozen_deck.py` 只读 `.inp`，把每行初应力分类为 `elset_plus_uniaxial` 或 `ccx_2_21_legal`。

### 8.3 实验

`artifacts/ic_format_audit.json`：两行都是 `elset_plus_uniaxial=true`、`ccx_2_21_legal=false`。格式化面层应力 `3.549611e+08` 等于写入器 \(\sigma_{\text{floor}}=H_{\text{floor}}/(16A)\)。

本机 `ccx -v` 打印 `This is Version 2.21`。对副本执行后，stdout 为：

```
*ERROR reading *INITIAL CONDITIONS. Card image:
       E_FLOOR_ROPE,3.549611E+08
...
*ERROR in calinput: at least one fatal
       error message while reading the
       input deck: CalculiX stops.
```

exit 201。产物：无 `job.frd`；`job.dat` 0 字节；`job.sta` / `job.cvg` 只有表头。本机墙钟 0.738–0.815 s，与已给「<1 s」一致。横幅 “number of:” 明确写着 “estimated upper bounds”，是读 deck 时的上界估计，**不是组装后的方程数**；全文无 equation count。原文件运行后哈希仍为 `82548e6a…276ab6da`。

上述事实先作为已给外部求解记录，再在本机复现。两份记录见 `artifacts/ccx_run_82548e6a.json` 以及 `ccx_82548e6a.stdout.txt` / `.sta` / `.cvg` / `.dat`。

`.sta` 全文：

```
SUMMARY OF JOB INFORMATION
  STEP      INC     ATT  ITRS     TOT TIME     STEP TIME      INC TIME
```

`.cvg` 同样只有收敛表头。

### 8.4 展望

以后若要把初应力写成单元号+积分点+六应力，那是**新** deck、**新**哈希。本文不把那次改写提前做进 `82548e6a`。

---

## 9. 张靖皋实验结果

### 9.1 相关工作

科学对象是一座桥的一份已发布中心线 STEP，不是通用算例。

### 9.2 方法

结果从冻结 deck、门 JSON、142 榀台账和 CalculiX 2.21 日志回读。不报告任何已完成步的位移、反力或频率。

### 9.3 实验

1. 坐标公约成立，未减 \(x_{\min}\)。
2. 拓扑对账：21 道横通道、**142 榀门架**，均来自 STEP 证据，插入 0 与 0。
3. 面层/门架锚在词法与集合上都分开（\(312\cap16=\emptyset\)）。
4. 独立垂度初值用 227.300 m；正文无 255.56。
5. 26 个自动门全部 PASS（`artifacts/coord_gate.json`）。
6. 单元测试 `test_coord_gate`、`test_write_inp`、`test_reconcile`、`test_audit_frozen_deck` 通过，且不改写 deck。
7. CalculiX 2.21 读 `TYPE=STRESS` 按已给方式失败；哈希未改。

写入 deck 的角色计数：`floor_rope` 25 299，`portal_or_beam` 4 719，`portal_rope` 227，`cross_passage` 21，`handrail_rope` 34，`longitudinal_other` 17。

### 9.4 展望

成立的科学主张是：存在一份带哈希、坐标过门、拓扑对账的 CalculiX 主 deck，并且这份 deck 在 ccx 2.21 上因初应力词法失败而未能组装。不成立的是十四阶复现。

---

## 10. 讨论与结论

### 10.1 相关工作

PR #18 交出空目录。PR #19 第一次放下带哈希的主 deck。本 run 补上 142 榀逐站台账、CalculiX 2.21 读入记录和完整论文，且不改 `82548e6a`。

### 10.2 方法

证据里看得见的有界项写成 bounds，不藏成未声明 FAIL。硬门（恒等变换、21/142 榀、锚分集、完整关键字、冻结哈希、禁源）全部闭合。

### 10.3 实验（有界项，不粉饰）

- 北锚是 STEP 端点代理，不是 K16+852 / K16+831。
- 门架索分类不完整（粗化后 227 个单元）；南门架锚取自 \(x=4221.093\) 的 `portal_or_beam`（距图纸 4225.700 为 4.61 m）。
- 几何垂度 214.18 m 对 227.30 m，过 15 m 门，但不是成型线拟合。
- 面层索总长约比四跨悬链估计长 20%；部分非面层中心线被标成 `floor_rope`。
- 高程直方图峰在 700 / 3023，不是鞍点；过门依据是鞍点邻域 \(Z_{p90}\)。
- 初应力卡对 ccx 2.21 不合法。求解器从未组装系统。没有谱。

### 10.4 结论

本 run 支持的主张可以一句说完：

> 从已发布 STEP 出发，在 \(x=\text{桩号}-K16+876.000\) 下可以生成一份可回读、带 SHA-256 `82548e6a` 的 CalculiX 主 deck；面层锚与门架锚分开；21 道横通道与 **142 榀门架**对账闭合且插入为 0；该冻结 deck 的 `TYPE=STRESS` 为 ELSET+单轴，CalculiX 2.21 读入失败（`E_FLOOR_ROPE,3.549611E+08`，exit 201），无 `.frd`、`.dat` 空、`.sta`/`.cvg` 仅表头、墙钟 <1 s、无方程数；哈希未改。

不支持的主张：已求解、十四阶同序复现、北锚已落到物理桩号、门架索分类已完整。

下一步若做，应是**新**哈希 deck（单元号+积分点+六应力），然后才是非线性静力，然后才是 TARGET-FREQ。那一步不属于 `82548e6a`。

---

## 复现

```bash
python3 catwalk-fem/tests/test_coord_gate.py
python3 catwalk-fem/tests/test_write_inp.py
python3 catwalk-fem/tests/test_reconcile.py
python3 catwalk-fem/tests/test_audit_frozen_deck.py
python3 catwalk-fem/pipeline/audit_frozen_deck.py
sha256sum -c catwalk-fem/artifacts/zjg_catwalk_coarsened.inp.sha256
cd catwalk-fem/paper && pdflatex -interaction=nonstopmode zjg_catwalk_agentic_fea.tex
```

不要把 77 MB STEP 入库。不要把 `isolated/TARGET-FREQ.json` 喂给写入器或求解器。不要改写 `zjg_catwalk_coarsened.inp`。

## 数据

本分支 `cursor/catwalk-main-deck-gate-f23d` 的 `catwalk-fem/artifacts/`。冻结 deck 哈希 `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da`。自评留痕 `catwalk-fem/eval/GROK_SELF_EVAL.md`。142 榀逐站表 `catwalk-fem/artifacts/portal_142_table.md`（单位：榀，不是槬）。

## 参考文献

1. G. Dhondt, *CalculiX CrunchiX USER'S MANUAL version 2.21*, 2023, §6.11.7, §7.76.
2. 张靖皋猫道十四项低阶模态独立理论建模与理论验证 v1.2，`catwalk-theory/thirteen-mode-models`，2026-08-08。
3. `catwalk-fem/SKILL.md`，`catwalk-fem/PLAN.md`，run `catwalk-main-deck-gate-f23d`。
4. Release `catwalk-attachment23-v2.0-s10-20260716`，`cw_S10_0716t050342_a4_centerline.step`，SHA-256 `d03d01e3…763344`。
5. 已给猫道计算：ccx 对 `82548e6a` 读入 `*INITIAL CONDITIONS` 失败（`E_FLOOR_ROPE,3.549611E+08`，exit 201）；本机 CalculiX 2.21 复现见 `artifacts/ccx_run_82548e6a.json`。

---

## 附录 A　142 榀门架逐站对账（不是槬）

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

完整 stdout：`artifacts/ccx_82548e6a.stdout.txt`。致命行：

```
*ERROR reading *INITIAL CONDITIONS. Card image:
       E_FLOOR_ROPE,3.549611E+08
*ERROR in calinput: at least one fatal
       error message while reading the
       input deck: CalculiX stops.
```

无 `.frd`。`.dat` 空。`.sta`/`.cvg` 仅表头。原 deck 哈希未改。
