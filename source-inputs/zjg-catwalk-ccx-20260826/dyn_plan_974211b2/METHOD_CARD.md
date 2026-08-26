# METHOD_CARD — CalculiX 2.21 题面（S1，0 ccx）

对象 ELF：`/workspace/bin/ccx`  
SHA-256：`3ca5c8d161047c6d646e5b34d86f0a04d90632f2c5f7d601018f1c9af49c4b59`（6964696 B，当场 `sha256sum`）  
手册：官方 `http://www.dhondt.de/ccx_2.21.pdf`（本岗下载核读，不编页码）。  
包装器 `/workspace/agentic-work/ccx` 与 2.23 ELF **禁止**。本 ELF 缺 `libgfortran.so.4`；运行时只设 `LD_LIBRARY_PATH=/workspace/lib` 加载同名库，**仍 exec** `/workspace/bin/ccx`，不走包装器。

`not_a_scientific_claim=true`。本卡只锁关键字，不宣布与附件频率的指标关系。不写符合。

---

## 1. 题面对照（方案 3.4 默认锁 → 手册原文）

| 题 | 方案默认锁 | 2.21 原文结论 | 本包动作 |
|---|---|---|---|
| T3D2 几何刚度是否进入 `*FREQUENCY` | 进入，当且仅当前一步 `NLGEOM` 切线被 `PERTURBATION` 继承 | 成立。§6.9.2：扰动步把上一非扰动静力步的位移与应力贡献加进刚度。§10.7.3：`iperturb=1` 时 `mafillsm.f` 计入 stress stiffness 与 large deformation stiffness。T3D2 与 B31 同类（铰接），B31 胀成 C3D8I；手册未把 T3D2 排除在应力刚度之外 | 正路保持 `NLGEOM` 父 + `PERTURBATION`。H-method 不因「单元类型不会做预应力模态」预先升格 |
| `*STEP, PERTURBATION` 是否必须 | 正路必须 | 成立。无扰动：频率在未加载结构上，前步无影响。有扰动：刚度被前一静力步增强 | 正路必须。`DYN_NOPERT` 为负对照 |
| 质量来源 | 只有 `*DENSITY`；GRAV 不是质量 | 成立。§7.35 `*DENSITY` 是材料质量。`*DLOAD` GRAV 是体力，要密度才能形成荷载，不进入质量矩阵 | 正路不改密度（S6 除外） |
| 默认特征值求解器 | ARPACK；数据行只有整数；求最低 \(n\) 阶 | **部分推翻。** 迭代特征值过程固定是 ARPACK。`SOLVER=` 是 **线性方程分解器**（SGI / PaStiX / PARDISO / SPOOLES / TAUCS / MATRIXSTORAGE），**不是** ARPACK vs LANCZOS。数据行 **可以** 有三字段：阶数、频带下界、频带上界（cycles/time）。内部仍只算第一字段那么多阶；若最高算出的频率低于上界，**不保证** 带内根收全。示例仍是单整数 `10` | 正路不写 `SOLVER=`，数据行只有整数 40。见下条 BAND |
| 频带语法 | 仅 `*FREQUENCY, SOLVER=LANCZOS` 的 `n, fmin, fmax` | **推翻。** 2.21 `*FREQUENCY` **没有** `SOLVER=LANCZOS`。LANCZOS 只出现在 `*BUCKLE` 的「Lanczos vectors」字段与内部 `mei[1]`。频带下/上界是 `*FREQUENCY` 自身数据行的第 2、3 字段，特征值过程仍是 ARPACK | **S1 未锁 LANCZOS。** 按方案 1.9.6 / 3.13 第 5 行：`DYN_BAND` **不发卡**，LEDGER=`BLOCKED`，0 ccx。禁止发明 `SOLVER=LANCZOS`。禁止把正路改成三字段 |
| 请求阶数 / 频带（正路） | 40、无频带 | 与手册示例同构（单整数 = 最低 \(n\) 阶） | 正路 40；N20 对照 20 |
| T3D2→C3D8I 参与系数 | 软读 | T3D2「similar to B31 except hinges」；B31 胀成 C3D8I。参与系数在胀实网格上，不当第二套频率 | `.dat` 频率权威；`.frd` 形状；参与软读 |
| 扰动步内追加 `*BOUNDARY` | FILT 允许，OP 默认 MOD，禁止 OP=NEW | §7.4：`OP=MOD` 默认，先前 SPC 保持；`OP=NEW` **去掉** 先前位移约束。齐次约束「should be placed before the first `*STEP`」 | FILT 仍按方案写在频率步、不写 `OP=`（即 MOD）。若求解器拒绝：该卡 `BLOCKED`，**不** 改名成 PIN_STATIC |
| 从模型定义省略 010 | 正路允许；111/011 保留 | 齐次约束写在模型定义。省略 010 只是少钉 UY，不是 `OP=NEW` | 正路 UYFREE。刚体则记账，默认不加弹簧 |

---

## 2. 原文摘录（不编页码；节号来自打开的 2.21 手册目录）

**§6.9.2 Frequency analysis**

> If the perturbation parameter is not activated on the `*STEP` card, the frequency analysis is performed on the unloaded structure, constrained by the homogeneous SPC’s and MPC’s. Any steps preceding the frequency step do not have any influence on the results.
>
> If the perturbation parameter is activated, the stiffness matrix is augmented by contributions resulting from the displacements and stresses at the end of the last non-perturbative static step, if any […].

**§7.62 `*FREQUENCY`**

> This procedure is used to determine eigenfrequencies and the corresponding eigenmodes of a structure. The frequency range of interest can be specified by entering its lower and upper value. However, internally only as many frequencies are calculated as requested in the first field beneath the `*FREQUENCY` keyword card. Accordingly, if the highest calculated frequency is smaller than the upper value of the requested frequency range, there is no guarantee that all eigenfrequencies within the requested range were calculated. If the PERTURBATION parameter is used in the `*STEP` card, the load active in the last `*STATIC` step, if any, will be taken as preload. Otherwise, no preload will be active.
>
> There are four optional parameters SOLVER, STORAGE, GLOBAL and CYCMPC. SOLVER specifies which solver is used to perform a decomposition of the linear equation system.
>
> For the iterative eigenvalue procedure ARPACK is used. The eigenfrequencies are always stored in file jobname.dat.
>
> Second line: Number of eigenfrequencies desired. / Lower value of requested eigenfrequency range (in cycles/time; default: 0). / Upper value of requested eigenfrequency range (in cycles/time; default: ∞).
>
> Example: `*FREQUENCY` / `10` — requests the calculation of the 10 lowest eigenfrequencies.

**§10.7.3 Frequency calculations**

> filling the stiffness and mass matrix in mafillsm.f. The stiffness matrix depends on the perturbation parameter: if iperturb=1 the stress stiffness and large deformation stiffness of the most recent static step is taken into account
>
> solving the eigenvalue system using SPOOLES and ARPACK

**§6.2.35 T3D2**

> This element is similar to the B31 beam element except that it cannot sustain bending. This is obtained by inserting hinges in each node of the element. […] instead of the `*BEAM SECTION` card the `*SOLID SECTION` card has to be used.

**§7.4 `*BOUNDARY`**

> OP can take the value NEW or MOD. OP=MOD is default and implies that previously prescribed displacements remain active in subsequent steps. […] OP=NEW implies that previously prescribed displacements are removed.
>
> Homogeneous conditions should be placed before the first `*STEP` keyword card.

**§7.35 `*DENSITY`** — 材料密度，质量矩阵来源。  
**`*DLOAD` GRAV** — 体力；要密度才能形成重力荷载，不是模态质量。

---

## 3. 本 ELF 锁死的正路关键字

```
*STEP, NLGEOM
*STATIC
… GRAV + 二期 …
*END STEP
*STEP, PERTURBATION
*FREQUENCY
40
*NODE FILE, NSET=N_MCT
U
*END STEP
```

- 不写 `SOLVER=`。
- 正路数据行只有整数 40。
- 不写 `STORAGE=YES`（不需要 `.eig`）。
- 频率步不写 `*NODE PRINT U`。
- 频率步与追加块禁止 `OP=NEW`。
- 执行注：`*NODE FILE, NSET=N_MCT` 在 T3D2 胀实后写出 0 条 DISP。女儿卡频率步 **额外** 写无 NSET 的 `*NODE FILE / U`，只改输出，不改 K/M/BC。S2 用胀实节点 DISP 按 (X,Z) 平均回原 nid。

---

## 4. BAND 裁决

| 项 | 值 |
|---|---|
| 2.21 是否存在 `*FREQUENCY, SOLVER=LANCZOS` | **否** |
| 三字段数据行是否合法 | 是（ARPACK 过程上的 n / fmin / fmax） |
| 方案 1.9.6 硬门 | 要么锁 LANCZOS，要么从可跑矩阵拿掉 |
| 本岗 | **未锁 LANCZOS** → `DYN_BAND` 不发卡，LEDGER `freq_status=BLOCKED`，0 ccx |
| 禁止 | 正路改三字段；发明 LANCZOS 参数；用 2.23 ELF 试 LANCZOS |

`lanczos_locked=false`

---

## 5. 单位

Deck 时间单位 s → `CYCLES/TIME` = Hz。g = 9806 mm/s²。密度 t/mm³。
