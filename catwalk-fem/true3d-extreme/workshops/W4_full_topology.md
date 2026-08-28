# W4 完整拓扑（R1–R7 已关）

本文件只记录**未缩减** deck，不覆盖 C4 `true3d_ccx.inp` / 图谱。

## 发出去的模型

- 脚本：`code/build_true3d_full.py`，作业名 `true3d_full`
- 44 根承重/门架索，T3D2（只受拉，对 LINK10/180）
- 门架/通道全部 BEAM188 → B31，ASEC 61–66；横梁全部保留
- CERIG UXYZ/ALL → `*EQUATION`；S10 的 D/CP/下拉索照抄
- ROTY 稳定文件加在 B31 节点上（R7 关）
- MASS21 仍折进 T3D2 密度：ccx 2.21 `TYPE=MASS` × `PERTURBATION` 会崩，这是求解器限制，不是几何契约
- 预应力：成桥线形上用 `*INITIAL CONDITIONS,TYPE=STRESS`（全局 PK2，1 个积分点）。温度收缩会再缩短约 0.6% 索长，已弃。直索探针 3 次迭代收敛。
- CERIG ALL（间距 80–800 mm）用 `*RIGID BODY` 按连通块；线性 `u_s=u_m` 运动学是错的。UXYZ/CP 仍是 UX/UY/UZ `*EQUATION`。

## 试算

- 膨胀后约 2.83e6 方程，spooles 能分解，峰值内存 ~12–15 GB
- 旧 deck：线性 CERIG ALL + 温度预应力 → 门架节点残力 10^15–10^31
- 当前 deck sha 见 `artifacts/true3d_model_manifest_full.json`

未收敛前不报频率，不写 STRUCTURAL_OK，不改 C4 图谱。
