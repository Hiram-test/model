# 审核基线（后续必须叠在这上面）

Grok / 任何后续提交的 parent 必须已经包含本文件列出的 wave-4 修复。
禁止从 `078e76b` 或仍写 `STRUCTURAL_OK` 的树上继续做新工件。

开工前：

```bash
cd catwalk-fem/true3d-extreme/code
python3 test_review_gates.py
```

必须 PASS，再写任何新代码或 artifacts。

## 已锁定的修复

- G-P4：`resid/W > 1e-6` 或前 100 阶有残差刚体 → **FAIL**；`conclusion_allowed=false`。禁止再写 `STRUCTURAL_OK`。
- 建模器：`deck_id_from_s10` 把 S10 `id≥100000` 挪出 `100000*(g+1)+k`。
- R5：`cluster_x_stations` 把 sec-63 的 63 个 x 站收成 21 根等效梁。
- 扭转：`_align_by_station_k`，禁止数组下标对齐。
- 安攀：`U10=66.7/1.05=63.5`。
- C 级：库与 `c_level_review.json` 都是 **15** 项。
- `*NODE PRINT,NSET=NSUPP` 打 RF，不要 `TOTALS`。

已求解 COARSEN=4 deck（63 通道、安攀扫探 63.0）要等重跑 S3–S5 才更新。图谱在 G-P4 FAIL 期间只作对照，不是结论。
