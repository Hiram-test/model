# S10 LINK180 POST1-only 字段说明

本目录只恢复既有 S10 LS2 平衡数据库并读取静力 RST，不执行新的结构计算。运行固定采用 SMP 单进程、`/POST1` 和 `/EXIT,NOSAVE`；源 DB/RST 在运行前后均按长度、UTC 时间和 SHA-256 复核。

## 轴力 CSV

- `s10_link180_axial_force_n.csv` 无标题且每行两列。
- 第一列 `element_id` 是 TYPE4 LINK180 单元号，为无量纲整数。
- 第二列 `axial_force_n` 是 `SMISC,1` 轴力，单位 N；正值表示受拉。
- 硬门禁要求 73,692 行、73,692 个唯一单元、零非法行和零非正轴力。

## 机器摘要

- `ACTUAL_COUNT` 是 POST1 中选中的 TYPE4 数量。
- `WRITTEN_COUNT` 是 APDL 写入 CSV 的记录数。
- `NONPOSITIVE_COUNT` 是轴力小于或等于零的记录数。
- `GATE_PASS` 仅在数量为 73,692 且非正计数为零时等于 1。
- `RESULT_LOAD_STEP` 与 `RESULT_TIME` 必须分别为 2 和 1.001。

## 源完整性

- `preflight.json` 记录执行前 DB/RST 身份、输入安全扫描和活动求解进程数。
- `postflight_source_integrity.json` 记录执行前后两个源文件身份逐字段比较。
- `source_integrity_passed=true` 只在长度、创建时间、修改时间和 SHA-256 全部不变时成立。

## 最终 QA

- `qa_summary.json` 的 `status=PASSED` 与 `gate_passed=true` 表示轴力、执行、结果集和源完整性门禁全部通过。
- `mapdl_warning_count` 与 `mapdl_error_count` 必须均为零。
- `exit_without_saving_confirmed=true` 表示独立 POST1 会话没有保存或覆盖源数据库。
- `artifact_hashes.sha256` 覆盖本目录除账本自身外全部普通文件。
