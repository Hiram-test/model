# C10 机器工件字段说明

本目录的 JSON/CSV 必须保持语法有效，因此注释集中在本文件。`status` 只描述对应工件的完成层级：`PASSED` 表示静态源证检查通过，`NOT_RUN` 或 `VALIDATION_PENDING` 表示没有数值求解结论。

- `conn_id`：稳定逻辑连接编号；一条编号始终对应父 S10 的一条 CERIG。
- `master_node` / `slave_node`：最终 S10 原节点号，绝不因 C10 重排。
- `aux_node`：仅 UXYZ 存在，范围 2029627–2032750，坐标字符串逐项复制 slave。
- `rigid_element`：TYPE72 direct-elimination rigid-beam 元素号。
- `joint_element`：仅 UXYZ 存在的 TYPE73 三平移 penalty general-joint 元素号。
- `penalty_n_per_mm`：平移绝对罚因子，单位 N/mm；全桥基准为 5E10。
- `dof_behavior`：UX/UY/UZ/RX/RY/RZ 逐项相对运动学；UXYZ 的转角不耦合或 slave 不具该转角自由度。
- `canonicalized_equals_source_bytes`：删除白名单新增块并恢复原 CERIG 后是否逐字节等于最终 S10。
- `numeric_rank_evaluated=false`：有限转动 MPC184 装配切线尚未由 MAPDL 形成，不能宣称秩门禁通过。
- `launch_allowed=false`：30 个单位测试和全桥数值门禁尚未完成，当前包只能审阅和后续验证。
- 所有坐标单位为 mm，力为 N，力矩为 N·mm，质量为 tonne，时间为 s。
