# MCT 从零复现（预应力在 MCT）

源文件用中文原名，不用 Unicode 转义当文件名：

`source/01_设计资料与规范/猫道 - 门架索合建模型2.mct`

SHA-256 `0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1`，448673 B。

归档目录 `03_猫道动力分析/MCT基准复现_V1.0/` 只做索引，旧 CSV 不是新主。

对照 ANSYS：S10 `.db` 抽不出就留痕迹，不编数。先静力 / 索力 / 预应力。只迁，不编。`760c0ee4` 不动。

```bash
python3 catwalk-fem/mct-from-zero/build.py
python3 catwalk-fem/tests/test_mct_from_zero.py
```
