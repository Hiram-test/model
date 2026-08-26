# C10 门禁字段字典

本字典解释 `status.json`、`5078_mapping_summary.json` 以及两份 SHA-256 账本。JSON 语法不支持注释，因此所有字段和值的用途、单位和约束集中在此说明。

## `status.json`

### 顶层身份与决策字段

- `schema_version`：状态结构版本；值 `1` 表示本门禁首版固定结构。
- `run_id`：稳定门禁类型标识；`C10_VALIDATION_GATE` 表示 C10 连接替换的验证门禁，不代表求解 Run。
- `run_name`：带 UTC 时间戳的唯一目录名，用于避免与其他审计混淆。
- `created_at_utc`：审计快照生成时刻，ISO 8601 UTC，尾缀 `Z` 表示零时区。
- `status`：证据状态；`VALIDATION_GATE_MISSING` 表示源映射可审计，但必需验证尚未完成。
- `decision`：启动决策；`REJECTED_TO_LAUNCH` 表示禁止启动 C10 MAPDL。
- `source_blocked`：是否因源文件不可得而阻断；`false` 明确排除 `SOURCE_BLOCKED` 口径。
- `mapping_audit_status`：5078→8202 静态映射审计；`PASS` 仅表示计数与字段闭合。
- `validation_gate_status`：数值验证总体状态；`MISSING` 表示不能进入求解。
- `mapdl_launch_allowed`：是否允许启动；`false` 是门禁的执行约束。
- `mapdl_execution_attempted`、`mapdl_started`：本次是否尝试或实际启动 MAPDL；均为 `false`，证明审计是只读操作。
- `generator_modified`：是否修改生成器；`false` 满足本任务禁止修改生成器的约束。
- `audit_mode`：审计模式；`READ_ONLY_EXISTING_EVIDENCE` 表示只复用既有证据。
- `next_action`：解除门禁的顺序要求；字符串要求先从正式 S10 生成纯连接差分，再完成全部验证。

### `mapping_closure`

- `logical_connection_count`：逻辑连接总数，单位为条；固定为 `5078`。
- `uxyz_logical_connection_count`：只约束三平移的 UXYZ 逻辑连接数，单位为条；为 `3124`。
- `all_logical_connection_count`：六自由度刚接 ALL 逻辑连接数，单位为条；为 `1954`。
- `generated_mpc184_element_count`：两类逻辑连接展开后的 MPC184 单元数，单位为个；`8202=3124×2+1954×1`。
- `mapping_mismatch_count`：语义、字段、展开数量或唯一单元号不一致的总数；`0` 是通过值。
- `stable_field_pair_count`：旧 CERIG 与新 MPC184 明细按行比较的稳定字段组数；`5078` 表示所有逻辑连接均比较。
- `stable_field_pair_mismatch_count`：`dof_label↔source_semantics`、system、assembly_name、reason 四组稳定字段任一不一致的行数；`0` 表示全对齐。
- `detail_copied`：是否把 5078 行明细复制进门禁目录；`false` 表示只引用，避免重复大文件。
- `legacy_detail_reference`：旧 CERIG 5078 行约束明细的绝对路径，用于与 MPC184 台账逐行配对。
- `detail_reference`：权威 CSV 明细的绝对路径；用于复核每条主从节点、语义和单元号。

### `boundary_contamination`

- `present`：是否存在越过 S10 单变量边界的非连接变化；`true` 表示已发现污染。
- `candidate_lineage`：受审候选谱系；`U00_C10_MPC_DIAGNOSTIC` 是 U00 再生连接线。
- `reference_lineage`：对比基准；`S10_FINAL_A30_BOUNDARY` 表示正式 S10 应继承的 A30 边界。
- `section_id`：污染截面编号；`61` 是门架下横梁 H175x175 的 ASEC。
- `difference`：具体差异；`IYY_IZZ_SWAPPED_IN_U00_CANDIDATE` 表示两惯性矩字段对调。
- `pure_connection_delta`：候选是否只改变连接；`false` 表示违反 C10 单变量要求。
- `launch_effect`：差异对启动的影响；`HARD_REJECT` 表示无条件拒绝当前候选。

### `required_validation.penalty_sweep`

- `absolute_penalty_values_n_per_mm`：五档罚刚度绝对值数组，单位 N/mm；依次为 `1E9、5E9、1E10、5E10、1E11`。
- `tier_count`：罚因子档数；`5` 必须与数组长度一致。
- `unit_load_case_count_per_tier`：每档的单位荷载/力矩工况数；`6` 对应三力与三力矩。
- `required_tier_case_pair_count`：要求的档位-工况组合数；`30=5×6`。
- `completed_tier_case_pair_count`：正式 C10 验证包中已闭合组合数；当前为 `0`。
- `target_translation_slip_limit_mm`：目标三平移最大相对滑移上限，单位 mm；`0.00001` 即 `1E-5 mm`。
- `status`：该子门禁状态；`MISSING` 表示完整扫描不存在。

### 其他验证子门禁

- `required_validation.full_bridge_adjacent_tier.target_physical_mode_frequency_change_limit_fraction`：全桥同一目标物理模态相邻罚因子档频率变化上限，比例值 `0.0005`。
- `target_physical_mode_frequency_change_limit_percent`：同一上限的百分数表示，`0.05` 的单位是 `%`。
- `required_validation.full_bridge_adjacent_tier.status`：全桥相邻档证据状态；`MISSING` 表示尚未闭合。
- `required_validation.matrix_conditioning.maximum_coefficient_ratio_degradation_vs_legacy`：相对旧基线允许的矩阵系数比最大恶化倍数；`10.0` 表示必须小于 `10×`。
- `required_validation.matrix_conditioning.status`：矩阵门禁状态；`MISSING` 表示没有同口径结果。
- `required_validation.full_bridge_static_gate.status`：全桥静力硬门禁总体状态；`MISSING` 表示尚未执行 C10 全桥求解。
- `required_validation.full_bridge_static_gate.checks`：逐项硬门禁数组；每项由 `id` 和 `acceptance` 构成。
- `checks[].id`：稳定的检查标识，分别覆盖 MAPDL ERROR、negative pivot、LS1、LS2、两阶段能量比、反力、质量、LINK180、拓扑、组件、模态闭合和频带完整性。
- `checks[].acceptance`：该检查的机器可读阈值；`EQUALS_0` 为零计数，`REQUIRED` 为必须收敛，`LESS_THAN_OR_EQUALS_*` 为数值上限，`EXACT_CLOSURE` 为数量完全相等，带 `UNLESS_PHYSICALLY_JUSTIFIED` 的唯一例外必须书面给出物理原因。
- `MAPDL_ERROR_COUNT`：MAPDL ERROR 数必须为 0。
- `NEGATIVE_PIVOT_COUNT`：negative pivot 数必须为 0。
- `LS1_CONVERGENCE`：第一荷载步必须收敛。
- `LS2_NO_STABILIZATION_HOLD_CONVERGENCE`：第二荷载步必须在无稳定化保持的条件下收敛。
- `LS1_ENDPOINT_ABS_STEN_OVER_SENE`：LS1 端点能量比绝对值必须 `<=1E-2`。
- `FULL_HISTORY_PEAK_ABS_STEN_OVER_SENE`：全历程能量比峰值绝对值必须 `<=1E-2`。
- `LS2_ABS_STEN_OVER_SENE`：LS2 能量比绝对值必须 `<=1E-8`。
- `GRAVITY_VERTICAL_REACTION_RELATIVE_ERROR`：重力与竖向反力相对误差必须 `<=1E-4`。
- `UNCHANGED_MASS_VARIANT_TOTAL_MASS_ERROR_TONNE`：不改质量变体的总质量误差必须 `<=1E-6 tonne`。
- `LINK180_NONPOSITIVE_AXIAL_FORCE_COUNT`：LINK180 非正轴力数必须为 0，除非存在书面物理解释。
- `ZERO_LENGTH_DUPLICATE_ENDPOINT_MISSING_NODE_COUNT`：零长、重复端点和缺节点合计必须为 0。
- `UNREGISTERED_CONSTRAINT_OR_COMPONENT_COUNT_DRIFT`：未登记约束或组件数量漂移必须为 0。
- `REQUESTED_MODES_ACTUAL_SETS_EXPORTED_FREQUENCIES_AND_VECTORS`：请求模态、实际 SET、频率和向量数量必须完全闭合。
- `ZERO_TO_0P35_HZ_BAND`：0 至 0.35 Hz 频带不得被模态阶数上限截断。
- `UNEXPLAINED_ZERO_FREQUENCY_OR_NEGATIVE_EIGENVALUE_COUNT`：未解释零频或负特征值必须为 0。

### 负证据、图纸和哈希闭合

- `historical_negative_evidence.penalty_absolute_value_n_per_mm`：历史失败路径使用的罚因子绝对值，`5E10 N/mm`。
- `run_id`：历史未完成 Run 的唯一标识；值为 `modal_20260714_0221_penalty5e10`。
- `termination`：最终终止事实；字符串明确记录第 983456 行 ERROR 由 ABT file 的用户请求触发，而不是把它描述为求解器自主 nonconvergence 终止。
- `ls1_status`：LS1 完成情况；`INCOMPLETE_WITH_CONVERGED_AND_UNCONVERGED_SUBSTEP_STATES` 表示既有收敛子步也有未收敛状态，但整体未完成。
- `result_validity`：该历史结果的门禁效力；`NOT_A_PASS_AND_NOT_PENALTY_CONVERGENCE_EVIDENCE` 表示不能用于通过 C10。
- `coefficient_ratio_message`：日志原文口径的机器化摘要；只记录系数比超过 `1E8` 的警告，不引申相对基线倍数。
- `relative_to_legacy_degradation_ratio_quantified`：是否已计算相对旧基线的矩阵系数比恶化倍数；`false` 表示 `<10×` 门禁仍缺证据。
- `evidence_reference`：0221 主 OUT 的绝对路径。
- `interpretation`：使用限制；该记录只证明 LS1 未完成，不支持 `5E10` 与发散之间的因果结论，也不能关闭任何 C10 验证项。
- `drawing_source_integration.source_exists`：下游图纸 PDF 是否存在；`true` 表示文件可读。
- `source_reference`：图纸 PDF 绝对路径。
- `source_sha256`：图纸 PDF 的 SHA-256，用于冻结具体版本。
- `mapping_rows_with_drawing_reference`：5078 行明细内含图号引用的行数；`0` 表示尚未集成。
- `drawing_source_integration.status`：`SOURCE_EXISTS_NOT_INTEGRATED` 区分“源已存在”和“台账已接入”。
- `hash_closure.source_hash_entry_count`：源哈希账本条目数；为 `15`。
- `source_hash_verified_count`：逐项复算通过的源条目数；为 `15`。
- `artifact_hash_entry_count_excluding_ledger`：产物账本条目数；为 `6`，不包含账本自身以避免自引用。
- `artifact_file_count_excluding_ledger`：目录中除产物账本外的实际文件数；为 `6`。
- `closed`：两侧计数和哈希是否全部闭合；`true` 表示 `15/15` 源与 `6/6` 产物均通过。

## `5078_mapping_summary.json`

- `schema_version`：映射摘要结构版本；值 `1`。
- `summary_type`：摘要用途；固定为 C10 的 5078 逻辑连接到 MPC184 闭合。
- `created_at_utc`：摘要创建 UTC 时间。
- `source_artifacts`：映射配对的两份权威明细及复制策略。
- `source_artifacts.legacy_constraints`：旧 CERIG 5078 行台账；含绝对路径、SHA-256 和不含表头的数据行数。
- `source_artifacts.mpc184_connections`：新 MPC184 5078 行台账；含绝对路径、SHA-256 和不含表头的数据行数。
- `source_artifacts.details_copied_into_gate`：是否复制两份明细；`false` 表示引用现有文件。
- `mapping.logical_connection_count`：两种源语义的逻辑连接总数。
- `mapping.uxyz`、`mapping.all`：分别记录 UXYZ 与 ALL 的逻辑数、每条展开单元数和展开后的 MPC184 数。
- `mpc184_elements_per_logical_connection`：单条逻辑连接展开系数；UXYZ 为 `2`，ALL 为 `1`。
- `generated_mpc184_element_count`：对应分组或总计的物理 MPC184 数。
- `closure_formula`：人可读闭合公式；`3124*2+1954*1=8202`。
- `stable_pair_fields`：逐行配对使用的稳定字段；节点号会因偏置节点插入变化，因此不作为 join 键。
- `stable_field_pair_count`：完成稳定字段配对的逻辑连接数；为 `5078`。
- `mapping_mismatch_count`：所有映射不一致数；`0` 为通过。
- `structural_checks.unique_mpc184_element_id_count`：唯一物理单元号数；为 `8202`。
- `duplicate_mpc184_element_id_count`：重复单元号数；为 `0`。
- `uxyz_missing_primary_element_id_count`、`uxyz_missing_offset_element_id_count`：UXYZ 缺主或偏置单元号的行数；均为 `0`。
- `all_missing_primary_element_id_count`：ALL 缺主单元号行数；为 `0`。
- `all_unexpected_offset_element_id_count`：ALL 错带偏置单元号行数；为 `0`。
- `unknown_source_semantics_count`：非 UXYZ/ALL 语义行数；为 `0`。
- `drawing_traceability.source_pdf_exists`：图纸 PDF 是否存在；为 `true`。
- `mapping_rows_with_drawing_reference`：含图号引用的映射行数；为 `0`。
- `integration_status`：图纸接入状态；`NOT_INTEGRATED` 表示不可声称逐连接图纸闭合。
- `limitations`：三个不可越权解释的限制：映射通过不等于验证通过、U00 候选含 SEC61 污染、本摘要未运行 MAPDL 或改生成器。

## 哈希账本格式

- `source_hashes.sha256`：每行由 64 位小写 SHA-256、两个空格和源文件绝对路径组成；15 行分别冻结任务书、U00 谱系/依赖/构建审计/摘要/映射明细/include、旧 CERIG 明细、S10 基准 include、S10 边界审计、0221 主 OUT/ERR 及图纸源。
- `artifact_hashes.sha256`：每行由 64 位小写 SHA-256、两个空格和门禁内相对文件名组成；覆盖除自身外的 6 个文件，避免不可解的自哈希循环。
- 64 位十六进制字符串是文件原始字节的 SHA-256；路径不参与哈希计算，只用于定位复核对象。
