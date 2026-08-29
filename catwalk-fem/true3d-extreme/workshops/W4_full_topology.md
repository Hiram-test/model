# W4 完整拓扑（R1–R7 已关）

本文件只记录**未缩减** deck，不覆盖 C4 `true3d_ccx.inp` / 图谱。

## 发出去的模型

- 脚本：`code/build_true3d_full.py`，作业名 `true3d_full`
- 44 根承重/门架索，T3D2（只受拉，对 LINK10/180）
- 门架/通道全部 BEAM188 → B31，ASEC 61–66；横梁全部保留
- CERIG 按 ANSYS 刚性域写成 `*EQUATION`，**没有**焊杆、SPRING2、`*RIGID BODY`：
  - 平移：`u_s = u_m + θ_m × (x_s − x_m)`（UXYZ 与 ALL 都带力臂）
  - ALL（门架梁→门架梁，1954）：再加 `θ_s = θ_m`
  - UXYZ（门架梁→索，3124）：只锁平移；T3D2 从节点没有转角
- S10 的 D/CP/下拉索照抄
- ROTY 稳定文件加在 B31 节点上（R7 关）
- MASS21 仍折进 T3D2 密度：ccx 2.21 `TYPE=MASS` × `PERTURBATION` 会崩，这是求解器限制，不是几何契约
- 预应力：成桥线形上用 `*INITIAL CONDITIONS,TYPE=STRESS`（全局 PK2，1 个积分点）。温度收缩会再缩短约 0.6% 索长，已弃。

旧 deck（焊杆 + SPRING2）运动学不是 S10，已删。

本作业**只算静力**（`*STEP, NLGEOM` + `*STATIC`）。不写 `*FREQUENCY` / `PERTURBATION`。
未收敛前不报频率，不写 STRUCTURAL_OK，不改 C4 图谱。

## 静力尝试（未完成，不是 G-P3）

Deck sha `07e34750…`。ccx 2.21。作业目录 `/cursor/stores/self/true3d_full_static/`（不覆盖 C4）。

2026-08-29T13:23:23Z 一次活着的 stdout（stdbuf 行缓冲）读到：

- cascade **INFO**（不是 ERROR）：线性与非线性 MPC 共用节点 `2029627` 方向 2
- increment 1 / iteration 1，步长 1.0
- **2,827,600** 方程，下三角非零元 **45,500,968**
- 对称 spooles，4 CPU，RSS 约 13.4 GB / 15 GB（无 swap）

约 5 分钟后环境把 `/workspace` 强制切到 `cursor/table41-fable5-diff-d416` 并杀掉 ccx。此前多次 stdout 停在 spooles factor。没有真实 `Job finished`。

14.66 s、17970 节点、0 单元的那次 `Job finished` 仍是假的，不能当 G-P3。

## 第一次牛顿残差（仍不是 G-P3）

2026-08-29T21:33:31Z 起的一次活着的作业（ccx 2.21，deck `07e34750…`）在约 5 分钟窗口内走完对称 spooles 分解，并打出 increment 1 / iteration 1 残差后再次被环境杀掉。`.sta` 仍空，无 `*ERROR`，无 `Job finished`。原文：`artifacts/true3d_full_static_iter1_20260829T213833Z.txt`。

打印值（iter 1，步长 1.0，未做自动切步）：

- average force = `7.0693969532375007e20`
- largest residual force = `4.0171203731160344e26` at **node 2005549 dof 1 (UX)**
- largest increment / correction of disp = `9.031428e6` (mm) at **node 2005544 dof 3 (UZ)**

节点定位（未改几何）：

| 节点 | xyz (mm) | 身份 |
|---|---|---|
| 2005549 | 996918.3, −23140.0, 249125.6 | `E_GATE_62_100` B31；CERIG UXYZ 主节点，从节点 26944（门架索，同 x/y，z−107 mm） |
| 2005544 | 996918.3, −17760.0, 249125.6 | 同一门架线 `E_GATE_62_100` B31 |
| 26944 | 996918.3, −23140.0, 249018.6 | `E_GANTRY` T3D2 节点 |

cascade INFO 节点 `2029627` 仍出现；deck 最大节点号是 `2029623`，该号不在 `*NODE` 里，当作求解器内部号，不是残差点。

这些力/位移不是物理量级（9 km 一阶修正）。作业在自动切步或 iteration 2 之前被杀，所以还不能判 solver 发散，也不能判收敛。G-P3 = FAIL（进程被杀）。不写频率，不写 STRUCTURAL_OK，不改 C4，不退回 B31 索或 R1–R7。
