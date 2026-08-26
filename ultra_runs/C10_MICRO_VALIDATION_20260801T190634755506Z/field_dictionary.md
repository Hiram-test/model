# 微算例执行字段说明

`RAW_EXECUTION_COMPLETED_PENDING_NUMERICAL_FINALIZATION` 只表示十二个外部进程均已返回，不表示数值或工程通过。`equation_counts` 按 MAPDL 输出出现顺序记录每次矩阵组装的方程数；`equation_count_constant=true` 要求至少出现一次且去重后只有一个值。`small_pivot`、`zero_pivot`、`negative_pivot`、`automatic_cnvtol_reset` 和 `fatal_marker` 均为禁止项。力单位为 N，长度为 mm，力矩为 N·mm，转角为 rad。
