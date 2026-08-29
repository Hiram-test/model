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

未收敛前不报频率，不写 STRUCTURAL_OK，不改 C4 图谱。
