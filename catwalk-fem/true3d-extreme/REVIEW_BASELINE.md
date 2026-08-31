# 审核基线（后续必须叠在这上面）

**硬锁 SHA（必为祖先）**：`3a4250e9f01f41c198967eaa685e497134573049`

Grok / 任何后续提交的 parent 必须已经包含该 SHA（wave-4 改完的树）。
检查：

```bash
git fetch origin cursor/agentic-catwalk-fea-d416
git merge-base --is-ancestor 3a4250e9f01f41c198967eaa685e497134573049 HEAD
# 必须成功（exit 0）。本分支是 3a4250e 上的线性历史，不是单提交压扁。
# 禁止把 git exit 128（对象缺失）或 1-commit squash 当成通过。
# 禁止 rebase/checkout 退回旧树，禁止从 078e76b / STRUCTURAL_OK 另起炉灶。
cd catwalk-fem/true3d-extreme/code
python3 test_review_gates.py
```

必须 PASS，再写任何新代码或 artifacts。

## 已锁定的修复（都在 3a4250e9 上，禁止回退）

- G-P4：`resid/W > 1e-6` 或前 100 阶有残差刚体 → **FAIL**；`conclusion_allowed=false`。禁止再写 `STRUCTURAL_OK`。
- 建模器：`deck_id_from_s10` 把 S10 `id≥100000` 挪出 `100000*(g+1)+k`。
- R5：`cluster_x_stations` 把 sec-63 的 63 个 x 站收成 21 根等效梁。
- 扭转：`_align_by_station_k`，禁止数组下标对齐。
- 安攀：`U10=66.7/1.05=63.5`。
- C 级：库与 `c_level_review.json` 都是 **15** 项。
- `*NODE PRINT,NSET=NSUPP` 打 RF，不要 `TOTALS`。
- COARSEN=2 附加档已跑（不覆盖 C4）：TA1 −7.49%，TS1 −1.61%，LS1 −1.02%，VA1 −0.36%（`coarsen2_shift.json`）。
- 主曲线 CV 3.43% < 5%（`atlas/master_surface_cv.json`）。
- C4 重跑后：21 通道，deck `5ebc64fa`，安攀 U10=63.5，G-P4 仍 FAIL（resid/W 4.85e-6）。

图谱在 G-P4 FAIL 期间只作对照，不是结论。
