# 有限刚度门架与横向通道生成摘要

## 已生成

- 门架：142 品，BEAM188 单元 4260 个。
- 横向通道：21 品；单品拆分模板 337 节点、633 杆件。
- 横向通道（含两端有限三角接口）：BEAM188 单元 13419 个。
- 新增节点总数：32750（其中方向节点 20803）。
- 逻辑连接：UXYZ高罚刚度组合连接=3124 个，ALL rigid beam=1954 个，总计 5078 个。
- UXYZ general joint：位移绝对罚因子=5.000000e+10 N/mm；独立小算例最大相对滑移=9.1944e-6 mm（门槛 1.0e-5 mm）。
- 实际 MPC184 单元：8202 个；新增单元总数：25881（BEAM188+MPC184）；CERIG=0、CP=0。
- 模块交点自动补点：116；搭接重复子边删除：12。

## dedicated station

实际站位来自权威 MCT gate 集中荷载 -21.556 kN（导轮组 9.196 + 横通道三角门架 12.36），
而不是旧的图纸链距比例映射。外部 CSV 可在后续修订，不需要改生成器。

| 通道 | gate_index | Y (mm) | CW1/CW2 门架 |
|---|---:|---:|---|
| H01 | 3 | 203913.650 | CW1_GATE_03 / CW2_GATE_03 |
| H02 | 6 | 374913.650 | CW1_GATE_06 / CW2_GATE_06 |
| H03 | 9 | 545913.650 | CW1_GATE_09 / CW2_GATE_09 |
| H04 | 14 | 882913.650 | CW1_GATE_14 / CW2_GATE_14 |
| H05 | 17 | 1053913.650 | CW1_GATE_17 / CW2_GATE_17 |
| H06 | 20 | 1224913.650 | CW1_GATE_20 / CW2_GATE_20 |
| H07 | 23 | 1395913.650 | CW1_GATE_23 / CW2_GATE_23 |
| H08 | 26 | 1546918.300 | CW1_GATE_26 / CW2_GATE_26 |
| H09 | 29 | 1703917.500 | CW1_GATE_29 / CW2_GATE_29 |
| H10 | 32 | 1854913.250 | CW1_GATE_32 / CW2_GATE_32 |
| H11 | 35 | 2005917.500 | CW1_GATE_35 / CW2_GATE_35 |
| H12 | 38 | 2162918.300 | CW1_GATE_38 / CW2_GATE_38 |
| H13 | 41 | 2313913.650 | CW1_GATE_41 / CW2_GATE_41 |
| H14 | 44 | 2484913.650 | CW1_GATE_44 / CW2_GATE_44 |
| H15 | 47 | 2655913.650 | CW1_GATE_47 / CW2_GATE_47 |
| H16 | 50 | 2826913.650 | CW1_GATE_50 / CW2_GATE_50 |
| H17 | 55 | 3183413.650 | CW1_GATE_55 / CW2_GATE_55 |
| H18 | 58 | 3363413.650 | CW1_GATE_58 / CW2_GATE_58 |
| H19 | 61 | 3543413.650 | CW1_GATE_61 / CW2_GATE_61 |
| H20 | 66 | 3887913.650 | CW1_GATE_66 / CW2_GATE_66 |
| H21 | 69 | 4058913.650 | CW1_GATE_69 / CW2_GATE_69 |

## 主模型集成时必须继续处理

1. 本 include 必须替代旧 `apply_gate_rigid_diaphragm_couplings_xlong.inp` 与
   `apply_crosspassage_lateral_couplings_xlong.inp`，不可与二者同时输入。
2. 新梁密度为 0；门架/横通道现有 MCT 集中质量尚未从原 MASS21 中移出。
   后续应按 `generated_elements.csv` 的体积/长度重新空间化，并闭合总质量、重心和转动惯量。
3. 横通道端部三角接口采用 PHI102x4 有限刚度扇形杆。该拓扑是对 dedicated triangular gate
   的明确等效，尚缺原设计节点释放/连接详图；后续应以模态和原图进一步校准，而不能声称局部应力精确。
4. ASEC 已完整写入 A/I/J/Iw/TKz/TKy/TSxz/TSxy；正式集成必须要求
   `anisotropic_section_axis_audit.csv` 全部为 PASS，并用 MAPDL 原生回读截面属性。
