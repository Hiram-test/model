# catwalk-fem

张靖皋施工猫道的 STEP → CalculiX `.inp` 管线，并执行坐标过门
\(x=\text{桩号}-K16+876.000\)。

几何只来自 Release `catwalk-attachment23-v2.0-s10-20260716` 的中心线 STEP。
材料、索力和工况来自图纸/复核报告。禁止读取同 Release 的 S10 `.db`。

```bash
python3 catwalk-fem/pipeline/run_pipeline.py \
  --step /tmp/catwalk-assets/cw_S10_0716t050342_a4_centerline.step \
  --artifacts catwalk-fem/artifacts
```

测试：

```bash
python3 catwalk-fem/tests/test_coord_gate.py
python3 catwalk-fem/tests/test_write_inp.py
```
