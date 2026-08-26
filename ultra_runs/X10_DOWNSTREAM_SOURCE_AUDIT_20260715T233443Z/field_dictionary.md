# 字段与台账说明

JSON 与 CSV 语法不支持注释，因此本文件作为 `status.json`、`09_target_mapping.csv` 及两份 SHA-256 台账的紧邻说明；不得向 JSON/CSV 内插入注释而破坏格式。

## `status.json`

- `schema_version`：本包结构版本；整数 `1` 表示首版 X10 下游来源审计结构。
- `run_id`：稳定任务标识；固定为 `X10_DOWNSTREAM_SOURCE_AUDIT`。
- `run_name`：带 UTC 时间戳的唯一包名。
- `created_at_utc`：创建基准时间，采用 ISO 8601 UTC 格式。
- `status`：包级完成状态；`COMPLETED_READ_ONLY_EVIDENCE_PACKAGE` 表示证据落盘、哈希闭合并封为只读。
- `decision.c20`：C20 缺口分类；`UPSTREAM_NOT_EXECUTED` 表示来源已存在，但上游尚未形成所需执行产物。
- `decision.d10`：D10 缺口分类；`LEDGER_NOT_INTEGRATED` 表示来源已存在，但尚未进入正式下游台账闭环。
- `decision.source_missing_rejected`：布尔值 `true` 表示已有原始 PDF 证据足以否定 `SOURCE_MISSING`。
- `decision.construction_detail_source_status`：构造来源存在性状态；`SOURCE_PRESENT` 表示指定图纸与复核报告可直接定位。
- `decision.strict_mac_status`：严格 MAC 的来源门；`HARD_SOURCE_EVIDENCE_BLOCK` 表示缺少源端数值向量，无法以推断替代。
- `construction_source_findings`：下拉、门架和下游解释的规范化摘要；仅描述来源结论，不声称模型已实现。
- `strict_mac_source_gate.reference_target_count`：来源目标总数，固定为 `14` 个。
- `strict_mac_source_gate.four_decimal_frequency_count`：具有四位小数频率的目标数，固定为 `14` 个。
- `strict_mac_source_gate.r19_2_coarse_plot_scope`：R19.2 图像证据范围；`EARLY_ORDER_MODES_ONLY` 表示只有早期阶次的粗略截图。
- `strict_mac_source_gate.full_node_double_precision_reference_vectors_available`：源端全节点双精度向量是否可用；`false` 表示不可用。
- `strict_mac_source_gate.strict_mac_computable`：是否具备严格 MAC 的输入条件；`false` 表示不具备。
- `strict_mac_source_gate.forced_computed_mode_assignment_allowed`：是否允许强配计算阶次；固定为 `false`。
- `target_mapping.path`：十四目标台账的相对路径。
- `target_mapping.data_row_count`：CSV 数据行数，不含表头，固定为 `14`。
- `target_mapping.matched_mode_all_blank`：全部 `matched_mode` 是否为空；固定为 `true`。
- `target_mapping.row_status`：所有行的统一未解析状态。
- `target_mapping.evidence_grade_counts`：A/B/C 证据等级计数，分别为 6/5/3，总和为 14。
- `target_mapping.grade_*_target_indices`：各等级对应的来源目标编号，使用 PDF 表 4-1 的 1 起算编号。
- `execution_guard`：只读审计边界；各布尔值记录未改来源、模型、脚本，未启动 MAPDL，且包内没有临时渲染图。
- `package_integrity`：来源台账、产物台账、旁接说明和只读封口状态；`artifact_ledger_excludes_itself` 为 `true`，避免自哈希悖论。

## `09_target_mapping.csv`

- `target_index`：抗风报告表 4-1 的来源目标序号，范围 1-14。
- `target_id`：可审计目标标识；标准物理标签沿用 LS/VA/LA/TA/VS/TS，三个笼统边跨目标依序记为 SIDE1/SIDE2/SIDE3。
- `source_frequency_hz`：来源频率，单位 Hz；按原表固定保留四位小数，不得以计算结果覆盖。
- `source_label`：原表物理标签；`边跨模态` 不扩写方向、对称性或波腹信息。
- `source_pdf_absolute_path`：唯一原始来源 PDF 的绝对路径；包内不复制原 PDF。
- `source_pdf_sha256`：原始来源 PDF 的 SHA-256 小写十六进制摘要，共 64 位。
- `frequency_table_pdf_page`：表 4-1 所在的 PDF 物理页码，1 起算；不是页脚印刷页码。
- `shape_figure_pdf_page`：粗略振型图所在 PDF 物理页码；没有独立图时保持空白。
- `evidence_level`：`A` 表示四位频率、物理标签和粗略图齐全；`B` 表示四位频率和物理标签存在但无粗略图/数值向量；`C` 表示只给出笼统“边跨模态”。任何等级都不等同于拥有严格 MAC 数值向量。
- `evidence_basis`：证据内容的短说明，绑定表号或图号，不引入计算结果。
- `source_vector_available`：源端全节点双精度向量是否可用；所有行为 `FALSE`。
- `strict_mac_status`：所有行固定为 `HARD_SOURCE_EVIDENCE_BLOCK`。
- `matched_mode`：计算阶次匹配结果；所有行必须为空，防止频率近邻硬配。
- `status`：所有行固定为 `UNRESOLVED_SOURCE_VECTOR_MISSING`，表示目标定义存在但严格映射所需源向量缺失。

## SHA-256 台账

- `source_hashes.sha256`：每行格式为“小写 SHA-256、两个空格、原始 PDF 绝对路径”；仅列三份直接来源。
- `artifact_hashes.sha256`：每行格式为“小写 SHA-256、两个空格、包内相对路径”；覆盖除台账自身外的全部包内文件。
