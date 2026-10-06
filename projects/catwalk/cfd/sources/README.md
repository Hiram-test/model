# 资料位置

计算源资料保存在此目录，原文件不随便携代码包重复打包。`geometry/audit_status.json` 记录主要文件 SHA-256。

- 原始图纸及 INP 来自 https://github.com/Hiram-test/model ，提交 `9b62c3e2c882bf2dd0001cb3b81943df7d4f5fea`；图纸来自 Release `zhangjinggao-full-20260729` 的归档。
- `catwalk_drawings_1225.pdf`：原始图纸；`full_line_beam4_crossbeam_mesh_xlong.inp`：三维结构模型。
- `wind_report.txt`：用户风洞报告的文字提取。`table_3_1.csv`：报告表 3-1 的数值，保留原精度。
- `source_audit.json`：报告尺寸及数据坐标转换核查。
- `software_versions.txt`：实际使用的软件版本。
- `table_5_8_user.csv`：第二组用户图片表5.8的25行转录，保留原图三位小数；不能与表3-1混用。
- 第二组图纸的毫米尺寸、1:8推定依据及未知细节见`../report/user_drawing_assumptions.md`和`../scripts/setup_user_drawing.py`。两张图片未以独立文件出现在运行环境，原图可在会话中查看；没有伪造原图文件或声称已找到其完整论文。
- `porousBafflePressure_v1912_actual.C`：所用 OpenFOAM 版本的官方边界条件实现，供核对；不是本项目自写求解代码。

主 CFD 流程只需要已冻结的 `geometry/model.json`，不需要重新下载整个 GitHub 大归档。重新运行 `audit_geometry.py` 才需要对应原始文件。
