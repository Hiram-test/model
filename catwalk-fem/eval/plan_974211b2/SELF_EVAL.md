# 本岗自评：974211b2 方案 + MCT 线形叠层

评估人：Cursor Grok 4.6。未向用户提问。不开新 PR。不合并。不改主。

| 用户句 | 本岗 | 依据 |
|---|---|---|
| 要有大纲 / 方案，落到 #19 能读到的路径 | **已写** | `catwalk-fem/eval/plan_974211b2/PLAN.md` |
| 建模按 MCT 线形叠 | **已执行** | `overlay.py`：四跨组扒线形，1123 根 TENSTR 叠 PK2 |
| 线形图纸没有就从 MCT 扒完再叠 | **成立** | 本树无线形图；源是 `0d18e3f7` MCT 体 |
| 对的是 CalculiX 自己的运营力 | **成立** | 对照 IC / 线性步 S，不是 ANSYS POST1 |
| 机构型，DISP 节点 0，S≈IC 不是平衡，最差 −19.1% | **已记** | PLAN §4；`ccx_mct_from_zero/ccx_run.json` worst 0.19061214708677 |
| 703.46 别再锁稿 | **不锁** | `overlay.json` `lock_manuscript=false`；PLAN 写明只是 F/A |
| 主仍 974211b2 | **成立** | sha256sum 同串；本轮未改写 |
| 760c0ee4 不动 | **成立** | 仍 `760c0ee4…b0585de9` |
| 不编 | **成立** | 无手写索力；S10 表保持 null |
| 不 push main、不开新 PR、不合并 | **本岗遵守** | 只推 #19 已有分支 |
| 不扭 demo-rl-calculix | **成立** | 未引用该算例 |

当场：

```
974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1  zjg_catwalk_migrate_main.inp
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  zjg_catwalk_cleared.inp
PK2 vs main ip1  max |rel| = 4.758e-07
eid 1 σ = 703.46055 N/mm²   lock_manuscript = false
```

本 VM 无 `ccx`，本轮不重跑求解器，不把 Job finished 写成已平衡。
