# H10 普通有限门架两索族端口凝聚

对象为 `CW1_GATE_32` 的 30 根 BEAM188，不含 H10 横向通道。16 个承重索点和 6 个门架索点分别用刚性截面虚功映射到 B/T 中心；只约束实际索点平动，不给索施加转角。

## 核心结论

中心转角全部自由凝聚后，B/T 两个平动端是球铰端口：6×6 K 只有一个正轴向模态和五个零模态。它可以作为原 property-3 TRUSS 的秩一轴向替代，但不能产生客观的 portal shear；原 TRUSS 与该 K6 只能二选一，不能叠加。

自由转角有限门架给出 `k_N=24,925.7008 N/mm`、`EA_eq=1.99405719e8 N`、`A_eq=967.989 mm2`。原 property-3 的 B161×161×8 等效面积为 4896 mm2，H10 处 `k=126,071.929 N/mm`；有限门架只有原刚度的 19.77%。因此可以替换，但不是无影响替换，50 个普通站全部更新后必须重新校核全桥模态。

对各普通站应使用同一 `EA_eq` 和该站 B→T 的实际方向、长度重新形成轴杆 K；不可把 H10 的全局 6×6 数值原样复制到有不同倾角的站位。21 个横通道站已由四端口 gate-passage K12 包含两品门架，不能再叠加本门架 K6。

保留转角的 `K12_gate_ports_6dof.csv` 可描述横桥 Sy 方向的 portal 行为，但 B/T 索点各自沿横桥 Y 共线，B_RY、T_RY 是不可观察钻转，所以顺桥 Sx 剪切仍是机制。K12 正常具有 6 个整体刚体模态和 2 个钻转零模态。

`K6_gate_translation_fixed_rotation_portal_N_per_mm.csv` 是截面转角受限的灵敏度上限。局部参数约为 `k_Sx=0`、`k_Sy=80.7156 N/mm`、`k_N=24,925.7008 N/mm`；其中两节点 Sy 剪切弹簧会在孤立刚体转动下产生伪能量，只能作包络，不能冒充正式客观连接。

## 文件

- `K6_gate_translation_free_rotation_N_per_mm.csv` / `_N_per_m.csv`：正式两平动端秩一轴向矩阵。
- `K12_gate_ports_6dof.csv`：保留可观察中心转角的门架矩阵。
- `Krel3_fixed_rotation_local_N_per_mm.csv`：局部 Sx、Sy、N 的固定转角 portal 上限。
- `equivalent_parameters.csv`：EA、等效面积、property-3 对比和 portal 参数。
- `H10_gate_only_condensed.npz`：上述矩阵和接口坐标的数据包。
- `H10_gate_beam188_elements.csv`、`H10_gate_internal_all_rigid_links.csv`、`H10_gate_rope_interface_mapping.csv`：正式提取明细。

## 质量

仅凝聚刚度；正式 APDL 的门架梁材料密度为 0。本结果不含质量，50 个普通站仍只保留既有门架/导轮集中质量一次。
