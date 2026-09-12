# 张靖皋猫道 Agentic FEA：坐标过门、完整 INP 与论文执行方案

> **当前执行回读（#19 主 `974211b2`）**  
> `catwalk-fem/eval/plan_974211b2/PLAN.md`：MCT 线形已扒完并回读预应力。  
> **送审逻辑主干（19 skill + 八块锁 + 影响矩阵/PSO）**  
> `catwalk-fem/eval/SCHEME_974211b2_LINE_OVERLAY.md`。不换主。`760c0ee4` 不动。下文是 STEP 历史稿，不是本轮执行对象。

本文件原是 STEP 坐标过门对话的方案。完成判据当时写成：**仓库里出现自洽的 CalculiX `.inp`，并且写出完整论文。**

定位：一篇 **agentic FEA** 论文，对象是悬索桥施工猫道；流程是从图纸/中心线翻模、索力迭代、静力计算到计算工况的全自动编排。实现落在 `Hiram-test/model` 的 `catwalk-fem/`（即用户所说的 catwalkskill 执行器），编排契约沿用已有 19 节点 `bridge-fem-skill-suite`。

## 0. 已核实的硬事实

| 项 | 事实 | 处置 |
|---|---|---|
| STEP | Release `catwalk-attachment23-v2.0-s10-20260716` 的 `cw_S10_0716t050342_a4_centerline.step`（SHA-256 `d03d01e3…763344`，77 MB） | 只当几何。禁止读同 Release 的 `cw_S10_0716t050342_a4_eq.db` |
| 单位 | `SI_UNIT(.MILLI.,.METRE.)` | 全部换成米再建模 |
| 坐标系 | STEP 几何 X∈[0, 4270.609] m，高程峰在 X≈650–760 与 X≈2920–3080，Zmax=350.312 m，Y 簇与 ±(21.45±(0.85+0.26k)) 对齐 | **恒等变换**。禁止再减 `xmin` |
| 约定 | \(x=\)桩号\(-K16+876.000\)，北→南为正；y 上游→下游；z 向上 | 节点、边界、荷载共用 |
| 既有 `write_inp` | 他处草稿用 `xs = X - xmin` 对站，会把 660/2960 对错 | 作废该平移 |
| 仓库现状 | 无 CalculiX inp、无对应 commit/PR | 本分支补齐并开 PR |
| TARGET-FREQ | 附件 2-3 十四频只允许冻结后对照 | 求解器与 `write_inp` 不得读取 |

## 1. 坐标过门（本对话主门）

通过条件（全部写入 `artifacts/coord_gate.json`）：

1. STEP 单位审计为毫米，输出节点为米。
2. 变换选择有证据：塔柱高点对准北鞍 \(x=666.679\)、南鞍 \(x=2953.321\)（CALC-INPUT，复核报告表 1-9）。若已对准，变换 = 恒等。
3. 写入 `.inp` 的节点 X 等于变换后的 STEP X，不得为了“从 0 开始”再平移。
4. 支承 NSET 的节点满足 \(|x-x_s|<\varepsilon\)，\(x_s\) 来自同一公约。
5. 工况荷载的作用节点 X 落在声明区间，合力与线荷载×长度闭合。
6. `.inp` 正文不含 TARGET-FREQ 数值。

名义四跨端点 \(x\in\{0,660,2960,3677,4180\}\) 与真实鞍点必须同时登记，不得静默混用。

## 2. 完整 `write_inp` 必须写出的块

先前草稿不完整。本方案要求一个可被 CalculiX 词法接受的 deck：

- `*HEADING`：写明坐标系、单位、几何源、禁止源。
- `*NODE`：米制，\(x=\)桩号\(-K16+876\)。
- `*NSET`：分站支承、分幅、分角色。
- `*ELEMENT`：索 `T3D2`，门架/通道/横梁 `B31`。
- `*MATERIAL` / `*ELASTIC` / `*DENSITY`：只来自图纸/复核报告/已登记假定。
- `*SOLID SECTION`（索）与 `*BEAM SECTION`（梁，含 n1）。
- `*BOUNDARY`：与 NSET 同一批站。
- `*INITIAL CONDITIONS, TYPE=STRESS`：由独立找形 \(H=wL^2/(8h)\) 得到，\(h=227.300\) m，不用 255.56 m，不用 S10.db。
- 工况步（自洽）：
  1. `LC-DEAD-PRESTRESS`：自重 + 二期恒载 + 初应力，`*NLGEOM`。
  2. `LC-PERSONNEL-UNIFORM`：在已声明的猫道面层 X 区间叠加人群。
  3. `LC-WIND-Y`：横桥向施工风，同一坐标系。
  4. `LC-FREQ`：在完成态切线刚度上求频；不读目标频率。
- 每个 `*CLOAD`/`*DLOAD` 在 `load_plan.json` 里有合力审计。

## 3. 管线（对应 19 skill）

```
N01 charter
  → N02–N04 源与图纸登记（本仓库用已发布 STEP + 理论包已冻结常数）
  → N05–N06 语义清单与抽象（索显式 / 网片等效质量 / 禁止镜像）
  → N07 几何：parse STEP → 坐标过门
  → N08 材料截面质量
  → N09 边界
  → N10 索力迭代（解析 H 为初值；非线性静力为正式找形）
  → N11 工况
  → N12–N13 离散与预求解门
  → N14 write_inp
  → N15–N17 解验证 / 独立校核（无 ccx 时只签发预求解门与解析校核，不伪称已求解）
  → N18 论文与发布
```

几何源是 STEP；属性源是图纸/复核报告。两源不得对倒。

## 4. 论文结构（每章：相关工作 / 方法 / 实验 / 展望）

1. 引言：agentic FEA 的技术难点 + 猫道对象难点  
2. 相关工作  
3. 章程、隔离协议与证据等级  
4. 翻模（N02–N07）  
5. 坐标系与拓扑过门（N07/N09）  
6. 材料、边界与索力迭代（N08–N10）  
7. 计算工况（N11）  
8. 求解器 deck 与预求解验证（N12–N14）  
9. 张靖皋实验与结果  
10. 讨论与结论  

理论 L0（\(f_n=n\sqrt{g/32h}\)）只作量级门，不把附件频率写进输入。

## 5. 明确不做

- 不把 S10 `.db`、B00、MCT、TARGET-FREQ 写进模型输入。
- 不把 demo-rl-calculix 的算例当作本桥验证。
- 不把 VM 跑通写成科学复现。
- 不把 255.56 m 主缆控制垂度当成猫道成型垂度。
- 不提交 77 MB STEP 本体；只引用 Release。

## 6. 交付物

- `catwalk-fem/pipeline/*.py`：可复跑管线  
- `catwalk-fem/artifacts/zjg_catwalk_coarsened.inp`：坐标过门后的 CalculiX deck  
- `catwalk-fem/artifacts/coord_gate.json` 与 `bc_lc_gate.json`  
- `catwalk-fem/paper/`：完整论文（TeX + 能编译则 PDF）  
- 本分支 PR
