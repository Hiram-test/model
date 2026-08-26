# b00_modal_properties_clean.csv 字段说明

该 CSV 无表头，共 59 行、每行 15 列；不在 CSV 内插入注释以保持有效性。

1. mode：模态号，整数 1..59。
2. frequency_hz：频率，单位 Hz，E24.16 文本精度。
3. generalized_mass：MAPDL 官方 generalized mass。
4–9. pfx、pfy、pfz、pfrotx、pfroty、pfrotz：六个全局方向 participation factor。
10–15. emx、emy、emz、emrotx、emroty、emrotz：六个全局方向 effective mass。
