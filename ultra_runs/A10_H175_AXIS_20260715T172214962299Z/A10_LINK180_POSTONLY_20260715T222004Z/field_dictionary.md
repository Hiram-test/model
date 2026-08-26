# A10 LINK180 POST1-only 审计字段说明

本目录仅恢复既有 A10 静态平衡数据库并读取静态 RST，不执行新的结构计算。运行采用 SMP 单进程，结束命令为无保存退出；源数据库和结果文件在运行前后均按 SHA-256、长度和 UTC 修改时间复核。

## `preflight.json`

- `status`：启动前安全预检状态；只有 `PASSED` 才允许执行。
- `execution_mode`：固定为 `POST1_ONLY_SMP1`，表示单进程通用后处理。
- `process_preflight`：记录预检时活动 MAPDL 和活动求解进程数；两者必须为零。
- `input_preflight`：记录 APDL 输入哈希、时间戳、行数、逐行注释审计和禁用命令扫描结果。
- `forbidden_solve_command_count`：精确结构计算命令数量，必须为零。
- `forbidden_solution_processor_command_count`：求解处理器入口命令数量，必须为零。
- `source_files`：两个只读源文件的相对路径、字节数、UTC 时间和 SHA-256。
- `source_protection`：记录独立目录、禁止数据库保存及运行后复核要求。
- `mapdl`：记录执行程序身份、SMP 模式和单进程约束。

## `a10_link180_axial_force_n.csv`

该文件故意不写标题，保证每行均为纯数值。两列定义如下：

1. `element_id`：TYPE 4 LINK180 单元号，为无量纲正整数。
2. `axial_force_n`：LINK180 的 `SMISC,1` 轴力，单位 N；正值代表受拉。

硬门禁要求文件恰有 73,692 行、单元号唯一且全部轴力严格大于 0 N。

## `a10_link180_summary.txt`

- `ACTUAL_COUNT`：MAPDL 在 LS2 最后结果集中选中的 TYPE 4 单元数。
- `WRITTEN_COUNT`：APDL 实际写入纯数值 CSV 的记录数。
- `NONPOSITIVE_COUNT`：轴力小于或等于 0 N 的记录数。
- `GATE_PASS`：仅当 `ACTUAL_COUNT=73692` 且 `NONPOSITIVE_COUNT=0` 时为 1。
- `MIN_FORCE_N`、`MIN_ELEMENT_ID`：最小轴力及其单元号。
- `MAX_FORCE_N`、`MAX_ELEMENT_ID`：最大轴力及其单元号。
- `RESULT_LOAD_STEP`、`RESULT_TIME`：读取结果集的载荷步和伪时间，必须为 2 和 1.001。

## `qa_summary.json`

- `status`：最终状态；只有全部结果门禁、OUT/ERR 门禁和源完整性门禁通过时才为 `PASSED`。
- `actual_count`、`csv_row_count`、`unique_element_count`：MAPDL、CSV 行数和唯一单元号三方闭合。
- `nonpositive_count`：非正轴力记录数，必须为零。
- `minimum_force_n`、`maximum_force_n`：外部解析 CSV 得到的轴力范围，单位 N。
- `mapdl_error_count`、`mapdl_warning_count`：独立 POST1 OUT/ERR 的错误与警告计数。
- `source_integrity_passed`：运行前后源文件长度、SHA-256 和 UTC 修改时间完全一致时为真。
- `input_forbidden_command_count`：再次扫描输入所得禁用命令总数，必须为零。
- `gate_passed`：上述全部条件的最终合取值。

## `postflight_source_integrity.json`

- `before`、`after`：分别记录执行前后源 DB/RST 的字节数、UTC 创建/修改时间和 SHA-256。
- `length_unchanged`、`creation_time_unchanged`、`last_write_time_unchanged`、`sha256_unchanged`：逐文件完整性比较结果。
- `source_integrity_passed`：两个源文件全部比较项均为真时为真。
- `exit_without_saving_confirmed`：主 OUT 明确出现无保存退出记录时为真。

## `attempt1_invalid_sentinel/`

首轮只读执行使用了超过 APDL 输入上限的 `1E300` 极值哨兵。MAPDL 将哨兵置零并产生两条 WARNING，因此首轮摘要最小值无效；首轮全部产物被原样移入该目录留痕。最终执行把哨兵改为合法的 `1E199`，再次完成输入预检和源哈希核验后独立运行。首轮 CSV 的数据不用于最终门禁。
