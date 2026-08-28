# 审核基线（后续必须叠在这上面）

对照提交：`ce82b54`（lock）+ `14a988d`（G-P4 诚实 FAIL）。
本文件按**树上实有代码**记账。没有的函数不得写成「已锁定的修复」。

开工前：

```bash
cd catwalk-fem/true3d-extreme/code
python3 test_review_gates.py
```

必须 PASS，再写任何新代码或 artifacts。

## 已在树上（可以当事实引用）

- G-P4：`resid/W = 1.42e-6 > 1e-6`，前 100 阶有 4 个残差刚体（已从 `modal_basis` 剔除）。
  `gate_status.json`：`pass=false`，`verdict=FAIL`，`conclusion_allowed=false`。
  禁止再写 `STRUCTURAL_OK`。图谱与工坊只作对照，不是结论章节。
- C 级：库与 `c_level_review.json` 都是 **15** 项（A16/B12/C15），全部 `unverified_C`。
- 扭转通道：`buffeting.py` 用 `ids % 100000` 的站号 k 对齐 IB/OB，不是数组下标对齐。
- 节点号契约：建模器 `nid = 100000*(g+1)+k`。CP 主从走 `mapped_node`。
- `*NODE PRINT,TOTALS` 已从 deck 去掉（ccx 2.21 会 segfault）。未改加 `NSET=NSUPP` 的 RF 打印。
- COARSEN=2 附加档已跑：TA1 −1.43%，TS1 −1.10%，LS1 −0.90%（`coarsen2_shift.json`）。
- 主曲线 CV：平稳最大相对误差 3.37% < 5%。

## 锁文件写了、树上没有（下一波才能做）

这些名字在 `ce82b54` 里被写成「已锁定的修复」，**源码里搜不到**：

- `deck_id_from_s10` — 未实现。S10 `id≥100000` 与 deck 号空间是否碰撞，要等 `s10_model.npz` 回读再改。
- `cluster_x_stations` — 未实现。已求解 C4 deck 仍是 63 个通道 x 站；**不得写「builder now clusters」**。
- `_align_by_station_k` — 无此函数名；站号对齐已在 `channel_operators`。
- 安攀库值仍是 `U10=63.0`（注记写了 66.7/1.05）。改成 63.5 必须连扫掠一起重跑，单改库会和 artifacts 分叉。
- `*NODE PRINT,NSET=NSUPP` 打 RF — 未加。不要在未复跑 ccx 前加回任何 `*NODE PRINT`。

已求解 COARSEN=4 deck（63 通道、安攀扫掠 63.0）保持原样，等显式重跑 S3–S5 才更新。
不是科学结论。
