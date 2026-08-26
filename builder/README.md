# 有限刚度门架 + 21 道完整横向通道生成器

## 运行

```powershell
python .\build_finite_gate_passage_apdl.py
```

默认读取：

- `02_CAD几何模型/Catwalk_FullLine_ANSYS_AIValidation_V1.0/gate_centerline_*.csv`
- `gate_rope_couplings.csv`、`nodes.csv`
- `output/freecad/cross_passage_local_coordinates/*_nodes.csv`、`*_edges.csv`
- `../audit/passage_station_authoritative_map.csv`

也可用 `--stations-csv` 传入外部 dedicated station CSV。生成器同时兼容 audit
权威总表和 `generated/resolved_dedicated_stations.csv` 的精简表头。

## 关键建模原则

1. 142 品门架均为 BEAM188 有限刚度梁，不再把 22 个索节点 CP 成共同平动。
2. 门架梁轴节点为 master、原 LINK 索节点为 slave，采用“偏置 direct-elimination `MPC184 rigid beam` + 共点 displacement-only `MPC184 general joint`”；joint 通过 `SECJOINT,PNLT,DISP,-5.0E10` 使用 5.0×10^10 N/mm 位移绝对罚因子，高精度保留三平移并释放索节点转角。
3. 立柱中心线端部与横梁轴线的焊接偏置采用 `MPC184 rigid beam` direct elimination，包含刚体转动。
4. 横通道按 `tail + middle + middle + adjustment + middle + mirrored tail` 装配。
5. 长杆在全部杆件交点、模块边界和 100 mm 尾段搭接处拆分；搭接重复边删除。
6. 每道横通道两条顶弦在两幅猫道各 16 根底索横向位置（共 64 点）拆分，
   并逐点连接 dedicated gate 下横梁分段 master；不是只连两个最外端。
7. 横通道端部另设 PHI102×4 有限刚度三角接口杆；短中心线偏置使用 `MPC184 rigid beam` direct elimination。
8. APDL XLong 坐标变换为 `X=CAD_y, Y=-CAD_x, Z=CAD_z`。

## 稳定标定组

| 组 | 材料号 | 截面号 | APDL 单元组件 |
|---|---:|---:|---|
| gate_bottom | 61 | 61 | GATE_BOTTOM_E |
| gate_top_post | 62 | 62 | GATE_TOPPOST_E |
| passage_chord152 | 63 | 63 | PASS_CHORD152_E |
| passage_frame102 | 64 | 64 | PASS_FRAME102_E |
| passage_brace51 | 65 | 65 | PASS_BRACE51_E |
| passage_rhs50x30 | 66 | 66 | PASS_RHS5030_E |

所有组初始 `EX=206000 MPa`、`PRXY=0.31`，密度为 0。后续可以只修改相应材料
的 EX，或只修改相应 ASEC，而不改变拓扑和编号。

## 截面局部轴与横向剪切

BEAM188 的 K 节点定义 I-J-K 平面，该平面包含 local-x 与 local-z；它并不直接定义
local-y。生成器因此令非竖杆的 local-z 对齐全局竖向，并按以下真实截面朝向写主惯性矩：

- H175：腹板高度 175 mm 沿 local-z，故 `Iyy=2.8164706458E7 mm^4` 为竖弯强轴，
  `Izz=9.8308997396E6 mm^4` 为侧弯弱轴；
- RHS50×30：CAD 实体的 30 mm 为竖高、50 mm 为水平宽度，故 `TKz/TKy=30/50 mm`、
  `Iyy=75232 mm^4`、`Izz=176672 mm^4`。

ASEC 按官方 14 项顺序完整写入 `A,Iyy,Iyz,Izz,Iw,J,CGy,CGz,SHy,SHz,TKz,TKy,TSxz,TSxy`。
BEAM188 的两个有效横向剪切刚度为
`Kxz=TSxz·G·A` 与 `Kxy=TSxy·G·A`，不再沿用 ASEC 缺项时的默认 1.0。

| 组 | TSxz | TSxy | 依据 |
|---|---:|---:|---|
| gate_bottom | 0.2363842696133852 | 0.6712958043168660 | MAPDL 2026 R1 同尺寸 BEAM-I 的 SCZZ/SCYY |
| gate_top_post | 0.4260313674227942 | 0.4260313674227942 | MAPDL 2026 R1 RHS160×160×4 BEAM-HREC |
| passage_chord152 | 0.5 | 0.5 | ANSYS 官方薄壁空心圆管基准 |
| passage_frame102 | 0.5 | 0.5 | ANSYS 官方薄壁空心圆管基准 |
| passage_brace51 | 0.5 | 0.5 | ANSYS 官方薄壁空心圆管基准 |
| passage_rhs50x30 | 0.2874280543410113 | 0.6098841965465526 | MAPDL 2026 R1 RHS50×30×4 BEAM-HREC |

官方定义见 [BEAM188](https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/ans_elem/Hlp_E_BEAM188.html)
与 [SECDATA](https://ansyshelp.ansys.com/public/views/secured/corp/v251/en/ans_cmd/Hlp_C_SECDATA.html)。

## 主要输出

- `generated/apply_finite_gates_and_passages_v2.inp`
- `generated/generated_nodes.csv`
- `generated/generated_elements.csv`
- `generated/anisotropic_section_axis_audit.csv`
- `generated/generated_constraints.csv`
- `generated/calibration_groups.csv`
- `generated/passage_template_nodes.csv`
- `generated/passage_template_elements.csv`
- `generated/build_audit.json`
- `generated/build_summary.md`
- `generated/syntax_smoke_audit.json`（ANSYS v261 PREP7：0 error、0 warning）

APDL 组件包括 `ALL_GATES/ALL_GATES_N`、`ALL_PASSAGES/ALL_PASSAGES_N`、六个
标定组、每品门架、每道横通道以及四个跨别横通道组件。

## 集成边界与已知风险

- 新 include 必须**替代**旧门架三平动 CP 和旧横通道 `CP,UY` include，禁止并用。
- 梁密度当前为 0；原 MCT 集中质量仍需独立空间化并闭合总质量、重心和惯量。
- PHI102×4 端部扇形杆是 dedicated triangular gate 的显式有限刚度等效；缺少
  原设计节点释放/焊接详图，因此可用于整体模态标定，不能直接声称局部应力精确。
- 共点 `MPC184 general joint` 只激活 UX/UY/UZ 并采用显式 5.0×10^10 N/mm 位移绝对罚因子；独立静力与线性摄动小算例的最大相对滑移为 9.1944×10^-6 mm，低于 1.0×10^-5 mm 验收门槛，但属于有限罚刚度近似而非数学零滑移。
- ASEC 的 A/I/J/Iw 来自解析公式，TKz/TKy 与 TSxz/TSxy 已显式封板；正式集成必须
  要求 `anisotropic_section_axis_audit.csv` 的 2698 根 H175 和 2898 根 RHS50×30
  全部为 `PASS`，并以 MAPDL 原生截面回读或单梁小算例复核。
- `passage_station_authoritative_map.csv` 是当前权威站位输入，gate_index 为：
  `3,6,9,14,17,20,23,26,29,32,35,38,41,44,47,50,55,58,61,66,69`。
