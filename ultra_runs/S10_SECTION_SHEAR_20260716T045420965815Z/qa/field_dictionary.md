# S10 字段字典

JSON 和 CSV 语法本身不支持注释，因此字段、单位与状态含义集中说明如下。

- `physical_change_family=ASEC_TRANSVERSE_SHEAR_FACTORS_FOR_SECTIONS_61_TO_66`：唯一物理变化是六条 SECDATA 追加字段7至14。
- `CGy/CGz/SHy/SHz=0`：六类对称截面的质心与剪切中心偏置为零，单位 mm。
- `TKz/TKy`：ASEC 外包络在 local-z/local-y 的尺寸，单位 mm；用于方向与截面映射审计。
- `TSxz/TSxy`：U01 在 MAPDL 2026 R1 中读取并由短梁挠度验证的无量纲剪切修正因子。
- `frozen_first_six_fields_identical=true`：A、Iyy、Iyz、Izz、Iw、J 的原数值字符串逐字保持。
- `status=PREPARED_*`：只表示输入封板，绝不表示 MAPDL 已启动或结果通过。
- `s10_section_modal_sene.csv`：每行16列，依次为阶次、全模型SENE、SEC61..66六组SENE、六组占比、六组能量和、六组能量和占比；能量单位N·mm，比例无量纲。
- `artifact_hashes.sha256`：最后生成且排除自身，之后不得修改本准备包。
