# H10 两品有限门架 + 一品完整横通道静力凝聚

本目录从 `apply_finite_gates_and_passages_v2.inp` 的 H10/CW1_GATE_32/CW2_GATE_32 提取 699 根 BEAM188，并保留门架—横通道的 74 条 `CERIG,ALL` 刚臂运动学。

四个索接口依次为 `B_L, T_L, B_R, T_R`。每组 16/6 个实际索节点只参与三平动相容：先按刚性截面 `u_i=u_c+theta_c×r_i` 做虚功一致映射，不给索节点增加转角；随后把四个中心转角作为内部自由度静力凝聚，得到 12×12 平动端刚度。

四组索点各自沿横桥向共线，因此每个中心绕横桥 Y 轴的钻转不会产生任何索点平动。K24 具有 6 个整体刚体模态和 4 个这种不可观测钻转，共 10 个零模态；用对称伪逆凝聚这些自由转角是预期运动学，不是局部机构。最终 K12 恰有 6 个刚体零模态和 6 个正变形模态。

源 APDL 的每条 ASEC `SECDATA` 只写 A/I/J 六项；本脚本按该文件的缺省 `TSxz=TSxy=1.0` 复现 BEAM188 Timoshenko 剪切刚度，不混入相邻生成脚本后来补充的 14 项截面修正。

## 推荐文件

- `K12_translation_ports.csv`：N-mm 制主 ROM 推荐矩阵，节点内顺序为 UX、UY、UZ；已投影清除数值噪声并保持六刚体模态。
- `K12_translation_ports_SI.csv`：完全相同的矩阵按 N/m 输出，SI 主 ROM 可直接读取。
- `H10_gate_passage_condensed.npz`：同时含 K12_N_per_mm、K12_N_per_m、凝聚前 K24、两套接口坐标及六广义弹簧。
- `generalized_springs.csv`：六个正交广义变形弹簧，`delta_j=g_j^T q`、`F_j=k_j delta_j`，可精确重构 K12。
- `six_axial_rods_fit.csv`：六根非负轴向杆的低保真拟合；误差见 `audit.json`，不应替代精确 K12。
- `H10_beam188_elements.csv`、`H10_internal_all_rigid_links.csv`、`H10_rope_interface_mapping.csv`：提取和连接审计清单。

## 质量口径

本次只凝聚刚度。源 APDL 的新梁密度为 0，未生成质量矩阵、未把横通道或门架集中质量再次计入，因此不会与既有 MASS21 重复。

## 单位与坐标

采用 N-mm 制；APDL 坐标为 X 顺桥、Y 横桥、Z 竖向。K12 的平动刚度统一为 N/mm；换成位移 m 时使用 `K_N_per_m=1000 K_N_per_mm`。K24 含转角时相应行列具有 N、N-mm 的混合量纲。
