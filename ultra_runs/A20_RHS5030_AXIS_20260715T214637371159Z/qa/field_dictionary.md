# A20 RHS50×30 方向台账字段说明

`rhs50_direction_ledger.csv` 是任务书要求的 2,898 根逐件正式源证台账。CSV/JSON 语法本身不支持注释，因此在此集中说明字段和固定值。

- `apdl_elem_id`：B00 冻结输入中的 BEAM188 元素号；必须唯一且共 2,898 个。
- `b00_n1`、`b00_n2`、`b00_orientation_node`：B00 冻结输入的 BEAM188 I、J、K 节点；K 只定义截面方向，不是物理连接节点。
- `u00_n1`、`u00_n2`、`u00_orientation_node`：U00 重建源链版本的对应 I、J、K 节点；生成器版本变化允许编号不同。
- `cross_version_node_ids_equal`：仅记录 B00/U00 节点号是否相同；`FALSE` 不代表几何或方向不一致，方向按元素号和单位轴另行硬核对。
- `element_line_number`：该 EN 命令在 B00 include 中的一基行号。
- `assembly_name`、`member`：U00 可执行源链重建时的构件身份。
- `cad_source_key=MD5_03_05_RHS50X30`：方向依据为 MD5-03/05 图纸驱动 CAD 生成逻辑。
- `cad_length_axis=transverse`：盒体长度沿横通道横向轴。
- `cad_width_50mm_axis=longitudinal`：50 mm 截面宽度沿桥纵向，对应 BEAM188 local-y。
- `cad_height_30mm_axis=vertical`：30 mm 截面高度沿全局竖向，对应 BEAM188 local-z。
- `local_*_global_*`：由 B00 I/J/K 恢复的右手单位轴方向余弦；无量纲。
- `abs_local_z_dot_global_z`：30 mm 高度轴与全局竖向的绝对点积；本门禁要求不小于 0.9999999999。
- `width_local_y_mm=50.0`、`height_local_z_mm=30.0`：截面外包络尺寸及其局部轴映射，单位 mm。
- `iyy_mm4=75232.0`、`izz_mm4=176672.0`：冻结 ASEC 主惯性矩，单位 mm⁴；Izz>Iyy 与 50 mm 宽、30 mm 高一致。
- `b00_matches_u00_source_axis=TRUE`：同一元素号的 B00 与 U00 重建源链 local-z 逐分量一致；不要求不同生成器版本的节点编号相同。
- `physical_axis_change_required=FALSE`：该元素在 A20 不需要修改 K 节点。
- `status=PASS_ALREADY_CORRECT`：图纸方向、生成逻辑、B00 实际轴和 U00 重建源链四者闭合。

`COMPLETED_NO_SOLVE_ALREADY_CORRECT` 只表示 A20 的轴源证门禁已完成且不存在轴单变量，不表示新做了一次 MAPDL 求解。因为候选输入与 B00 字节相同，重复求解不会产生新的物理证据。
