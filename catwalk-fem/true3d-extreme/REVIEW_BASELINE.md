# 审核基线（后续必须叠在这上面）

对照：`ce82b54` lock → `14a988d` G-P4 FAIL → `926c6a6` `test_review_gates.py`。
开工前：

```bash
cd catwalk-fem/true3d-extreme/code
python3 test_review_gates.py
```

必须 PASS。禁止再写 `STRUCTURAL_OK`。禁止从 G-P4 FAIL 的树上写结论章节。

## 已在树上

- G-P4 FAIL：`resid/W = 1.42e-6 > 1e-6`，前 100 阶 4 个残差刚体已从 `modal_basis` 剔除。
  `conclusion_allowed=false`。
- C 级 **15** 项，全部 `unverified_C`。
- `deck_id_from_s10`：S10 `id≥100000` → `2000000+id`，避开 `100000*(g+1)+k`。
- `cluster_x_stations`：sec-63 近距 x 站收成等效梁。**已求解 C4 deck 仍是 63 站**，要等重跑 S3。
- `_align_by_station_k`：按站号 k 对齐，禁止数组下标对齐。
- `*NODE PRINT, NSET=NSUPP` 打 RF；不要 `TOTALS`。
- 安攀库值改为 `U10=66.7/1.05=63.5`。扫掠 CSV 仍是 63.0，等 S5。
- COARSEN=2：TA1 −1.43%，TS1 −1.10%，LS1 −0.90%。
- 主曲线 CV 3.37% < 5%。

已求解 COARSEN=4 deck（63 通道、安攀扫掠 63.0）保持原样，等显式重跑 S3–S5。
不是科学结论。
