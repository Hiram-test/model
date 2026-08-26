# C10 机器工件字段说明

本目录的 JSON/CSV 必须保持语法有效，因此注释集中在本文件。`status` 只描述对应工件的完成层级：`PASSED` 表示静态源证检查通过，`NOT_RUN` 或 `VALIDATION_PENDING` 表示没有数值求解结论。

- `conn_id`：稳定逻辑连接编号；一条编号始终对应父 S10 的一条 CERIG。
- `master_node` / `slave_node`：最终 S10 原节点号，绝不因 C10 重排。
- `aux_node`：兼容旧表结构而保留，单 TYPE72 方案中全部为空；任何非空值都应拒绝。
- `rigid_element`：一条逻辑连接唯一对应的 TYPE72 direct-elimination rigid-beam 元素号。
- `translation_link_element`：兼容旧表结构而保留，当前全部为空且 TYPE73 计数必须为零。
- `penalty_n_per_mm=null`：当前方案不存在罚刚度参数，也不存在罚函数滑移。
- `dof_behavior`：UX/UY/UZ 为物理刚体平移；UXYZ 的 RX/RY/RZ 只在 TYPE72 内代数闭合，源审计证明其物理共轭项为零。
- `uxyz_slave_projection_audit.json`：证明 3,124 个 UXYZ slave 只连接 LINK10/LINK180 和仅平移 MASS21，且与 D、CP、CE、力矩载荷零重叠。
- `canonicalized_equals_source_bytes`：删除白名单新增块并恢复原 CERIG 后是否逐字节等于最终 S10。
- `numeric_rank_evaluated=false`：有限转动 MPC184 装配切线尚未由 MAPDL 形成，不能宣称秩门禁通过。
- `launch_allowed=false`：12 个生产拓扑/有限转动/ALL 微测和全桥数值门禁尚未完成，当前包只能审阅和后续验证。
- 所有坐标单位为 mm，力为 N，力矩为 N·mm，质量为 tonne，时间为 s。
