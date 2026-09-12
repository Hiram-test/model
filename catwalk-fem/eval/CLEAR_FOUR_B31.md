# 清掉 4 个无约束 B31 分量（c635dad7 不过门现场不动）

评估人：Cursor Grok 4.6。未向用户提问。不 push。不合并。不交计算。  
41fb3222 不动。c635dad7 当不过门现场不动。新哈希写进本地 #19 账本后做独立回读。

## 1. 不过门依据（用户已给，本岗复算成立）

现场：`catwalk-fem/artifacts/zjg_catwalk_main.inp`  
SHA-256 `c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84`  
47 948 333 B。与声称一致。未改写。

本岗独立复算（`pipeline/reread_cleared.py`，`eval/INDEPENDENT_REREAD_760c0ee4.json`）：

| 分量 | 节点 | \(x\) | 单元 | 类型 |
|---|---|---|---|---|
| UNC0 | 9520, 9521 | 656.361709 | 25520 | B31 |
| UNC1 | 9518, 9519 | 656.361709 | 27932 | B31 |
| UNC2 | 33170, 33171, 33174, 33175 | 2965.36006–2968.194535 | 26301, 26302, 51699 | B31 |
| UNC3 | 33168, 33169, 33172, 33173 | 2965.36006–2968.194535 | 28713, 28714, 51698 | B31 |

12 节点：`9518 9519 9520 9521 33168–33175`。  
8 个 B31。钉 `N_ORPHAN_UNCONSTRAINED` 3596 点后仍剩这 4 个无约束**分量**。不是 21426 个无约束节点。不当计算主。

IC：421 432 行，全是 eid+ip+六 PK2，0 行 ELSET。连通 1073 分量 / 477 个 2 节点碎片。

## 2. 清法（另写路径，不覆盖三张冻结现场）

脚本：`pipeline/clear_four_b31.py`  
源必须是 c635dad7。目的地禁止是 `zjg_catwalk_coarsened.inp` / `zjg_catwalk_ccx221.inp` / `zjg_catwalk_main.inp`。

写入 `*NSET, NSET=N_CLEAR_FOUR_B31`（12 节点）与 `*BOUNDARY` UX,UY,UZ，插在 `*INITIAL CONDITIONS` 之前。不改节点、单元、IC 行。

新路径：`catwalk-fem/artifacts/zjg_catwalk_cleared.inp`

```
$ sha256sum catwalk-fem/artifacts/zjg_catwalk_cleared.inp
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  catwalk-fem/artifacts/zjg_catwalk_cleared.inp
```

47 948 916 B。sidecar 第一字段同一字符串。

## 3. 独立回读（清后）

| 项 | 值 |
|---|---|
| 无约束分量 | **0** |
| IC 行 | 421 432 八字段，0 ELSET |
| 八积分点 | 52 679 个 T3D2/B31 各写 1–8 |
| 面层∩门架 | 0（312 ∪ 16） |
| `E_CROSS_PASSAGE` | **42**（旧 21 + 新 21） |
| 图纸 deg-1 stub | **28**（−23.895×12 / −44.909×12 / 4225.700×4） |
| 标题 21 / 142 榀 | 有；榀 U+6980；榌只出现在「not 榌」 |
| `N_ORPHAN_UNCONSTRAINED` | 仍 3596 |
| 节点 / 单元 | 51924 / 52679 |
| CalculiX | **未跑**（`ccx_ran=false`） |

冻结三现场当场 `sha256sum` 仍为已给值。

有界项（用户已给，本岗复算仍真）：T3D2/B31 仍写 8 积分点；北/南门架图纸坐标是 28 个新 deg-1 节点接上去的；`E_CROSS_PASSAGE` 42。

## 4. 不当计算主

760c0ee4 清掉了 4 个无约束分量。本轮不交 CalculiX。不声称已求解。不打开 TARGET-FREQ。
