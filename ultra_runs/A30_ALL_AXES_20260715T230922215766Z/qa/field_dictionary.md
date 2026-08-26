# A30 等价包字段说明

- `COMPLETED_BY_INPUT_IDENTITY_WITH_A10_RESULTS`：A30 没有另起一份相同输入的 MAPDL 作业；它以字节级证据复用已经从头完成的 A10 静力—保持—80 阶模态结果。
- `physical_axis_families_complete=2`：H175 轴由 A10 修正；RHS50×30 由 A20 证明 B00 已正确、改动数为零。
- `combined_dependency_identity`：按 11 个 include 的顺序、文件名和 SHA-256 拼接后再计算的组合身份。
- `byte_identical_a30_candidate_to_a10=true`：A30 合并物理定义不会在 A10 之外增加任何输入字节变化。
- `duplicate_solver_run_required=false`：重复运行相同输入不会增加因果信息；A10 的 LS1、LS2、OUT/ERR、LINK180、80 阶、六组件 SENE 和全节点向量已独立复核。
- `taskbook_full_static_gate_status`：端点静力与数值门禁通过，但 RST 未保存 LS1 全历程逐子步 VENG，因此不得填写或声称全历程峰值 STEN/SENE。
- `target_physical_mapping_status`：十四目标定义和 80 阶候选池闭合；当前没有方向、跨别、S/A、波腹描述量和报告 R19.2 源向量 MAC，因此物理 mapping 保持未封板。
- `critical_results`：A10 的平衡 DB、模态 DB、RST、RSTP、MODE、FULL、RDB、LDHI 当前哈希与 finalizer 全 run 账本一致。
- `read_only_source_integrity`：LINK180 与六组件 SENE 两次 POSTONLY 使用的四个源 DB/RST 在运行前后以及 A30 QA 当下均保持相同 SHA-256。
- `parent_run_metadata_audit`：A10/A20 父运行内全部普通文件的相对路径、字节数与纳秒修改时间在 A30 QA 前后完全相同；摘要不包含访问时间，避免只读操作自身造成伪漂移。

JSON 语法不支持注释，因此本文件解释固定状态、布尔值和组合身份的含义。
