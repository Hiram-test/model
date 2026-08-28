# W4 完整拓扑（R1–R7 已关）

本文件只记录**未缩减** deck，不覆盖 C4 `true3d_ccx.inp` / 图谱。

## 发出去的模型

- 脚本：`code/build_true3d_full.py`，作业名 `true3d_full`
- 44 根承重/门架索，T3D2（只受拉，对 LINK10/180）
- 门架/通道全部 BEAM188 → B31，ASEC 61–66；横梁全部保留
- CERIG UXYZ/ALL → `*EQUATION`；S10 的 D/CP/下拉索照抄
- ROTY 稳定文件加在 B31 节点上（R7 关）
- MASS21 仍折进 T3D2 密度：ccx 2.21 `TYPE=MASS` × `PERTURBATION` 会崩，这是求解器限制，不是几何契约
- 预应力：T3D2 上 `*INITIAL CONDITIONS,TYPE=STRESS` 在 2.21 里不收敛（2 杆探针已复现）；改为温度预应力 σ = Eα|ΔT|

## 本机第一次试算（pod 重启前）

- 膨胀后约 2.83e6 方程，spooles 能分解，峰值内存 ~12–15 GB
- `TYPE=STRESS` 第一迭代残力 ~1e24，已弃
- 温度预应力 + 全步长 1.0：第一迭代残力仍 ~1e15，平均力 ~8e9；随后环境重启，求解中断
- 当前 deck 把静力第一步改成 0.05，让 Newton 自己切步

未收敛前不报频率，不写 STRUCTURAL_OK，不改 C4 图谱。
