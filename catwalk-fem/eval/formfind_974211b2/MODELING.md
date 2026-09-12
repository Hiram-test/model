# 建模岗：找形锁力 + 六工况卡 + 动力卡（不成稿）

本文件是工况卡与求解账，不是论文。论文岗成稿。不成附件对照结论。

主 `974211b2` 未改。P1 `be533c5f` = 只加 `*STEP, NLGEOM`。

## 初始锁力（已确定）

独立控制量 = MCT 成型线形。初始锁力 = MCT `*INIFORCE` / `*INI-EFORCE` mean，1123 根 TENSTR。
71 榀门架 TRUSS 无锁力，不编，门不对也不停。
不用表5-4 的 9309.3 / 581.8。

- n = 1123
- min/max/mean kN = {'n': 1123, 'min': 1482.74, 'max': 15724.3, 'mean': 7966.671006233303, 'p50': 10261.5, 'p95': 11075.75}

## 工况1 找形门（自判）

- CCX Umax = 42.25864819934656 mm @ nid 304
- 复核报告工况1 USUM = 42.57771305336941 mm @ 304
- vs 复核单元轴力 = {'n_compared': 1123, 'p50': 1.3080472901459605e-05, 'p95': 0.00012078609895670757, 'max': 0.0003163794398685856, 'worst_eid': 1058, 'named_1': {'ccx_N': 15705132.084332483, 'table_N': 15706172.0}}
- vs MCT 锁力 = {'n_compared': 1123, 'p50': 0.0015828780666949551, 'p95': 0.00309473219662297, 'max': 0.003279908458652224, 'worst_eid': 1070, 'named_1': {'ccx_N': 15705132.084332483, 'table_N': 15686250.0}}
- 门: `PASS`。过了就让论文岗写找形层。建模岗不停，接着六工况和动力。

P2–P6 是 P1 后再加第二步 NLGEOM（施工/风/温）。门架索峰值对不上也不停。

## 六工况卡（恒载/施工/温/风已有，从 MCT 刮，不编）

| ID | 组合 | 加的 STLDCASE | 风 | temp | sha256 |
|---|---|---|---|---|---|
| P1 | 工况1恒载 | [] | False | None | `be533c5f3228aacf` |
| P2 | 工况2 恒+施工 | ['施工荷载'] | False | None | `e364e0cdadbd9cf3` |
| P3 | 工可3恒+施工+温度 | ['施工荷载'] | False | -15.0 | `5477bf07f696f90b` |
| P4 | 工可4恒+施工+施工风 | ['施工荷载', '施工风荷载'] | True | None | `f2547fa950f337fd` |
| P5 | 工况5恒+最大阵风 | ['最大阵风'] | True | None | `7942a912070c5022` |
| P6 | 工况6恒+施工+温34 | ['施工荷载'] | False | -34.0 | `72622a0050c161da` |

施工风 ΣFY=2246.926048 kN，ΣFZ=-242.4709689 kN，n_fy=1123（横载+进风已在 MCT，P4 已加）。
最大阵风 ΣFY=15303.735373 kN，ΣFZ=-1651.461417 kN（P5）。
二维 UY 钉死，FY 进反力；面内差主要来自风的 FZ。

## 六工况求解（对复核；门架峰值不对也不停）

| ID | CCX Umax mm @ nid | 复核 USUM mm @ nid | rel | 峰点同 |
|---|---|---|---|---|
| P1 | 42.25864819934656 @ 304 | 42.57771305336941 @ 304 | 0.007 | True |
| P2 | 1621.1710000071648 @ 302 | 2684.837902342347 @ 1176 | 0.396 | False |
| P3 | 2414.1200002000473 @ 302 | 1910.0116845522327 @ 1176 | 0.264 | False |
| P4 | 1424.0670000002087 @ 302 | 2870.9665987120216 @ 1176 | 0.504 | False |
| P5 | 3059.4520001666783 @ 302 | 1335.7734445522826 @ 306 | 1.290 | False |
| P6 | 3421.501000607643 @ 302 | 927.4138039940444 @ 1166 | 2.689 | False |

P1 对上。P2–P6 量级在米级，峰点多在 302 不是复核门架索 1176/306。CONTINUE，不当门停。

## 动力卡

- `catwalk-fem/eval/formfind_974211b2/daughters/migrate_DYN.inp` sha `0fea45d6891428167a433512133b8214f7246c3e9b12ba906c9dcb067b2b72c3`
- P1 NLGEOM 后 `*STEP, PERTURBATION` + `*FREQUENCY` 20 阶
- 不读 `isolated/TARGET-FREQ.json`，不把 0.0296… 写进 inp
- 已解析阶数 20；不跟附件频率表对分

## 求解

- P1: {'ran': True, 'reused_existing': True, 'exit': 0, 'sha256.dat': 'bb7f5595b397300b246c7bdcacee53115a3283484d5c358a9cd8a403605b5fd7', 'sha256.sta': '4ab47f724c0ad1289736843a05bbee326354a6ab8018c080fa63c9ab003deb6a'}
- P2: {'ran': True, 'reused_existing': True, 'exit': 0, 'sha256.dat': 'ed3a36d6f2694db969fd6bc4401899373cb5761aafdf77bdc05df47be0c40e6b', 'sha256.sta': '00fe4e443d96ecd2567441bea4efe762470eb61c2ba035fc60c60473088de62a'}
- P3: {'ran': True, 'reused_existing': True, 'exit': 0, 'sha256.dat': 'e2215bd516961668c5ce764c00e27f19eec5070d21270e44daf1107c5464e63f', 'sha256.sta': '00fe4e443d96ecd2567441bea4efe762470eb61c2ba035fc60c60473088de62a'}
- P4: {'ran': True, 'reused_existing': True, 'exit': 0, 'sha256.dat': '026b8d1cf20cfe88cca1177ea20d3a8780b8a3770abc869835e0429e83a8b753', 'sha256.sta': '00fe4e443d96ecd2567441bea4efe762470eb61c2ba035fc60c60473088de62a'}
- P5: {'ran': True, 'reused_existing': True, 'exit': 0, 'sha256.dat': '6ed9f5b1cd0dd395ec0a6a4a8c738ed7c0745e12a6e1a836a6b1b67d8e695105', 'sha256.sta': '00fe4e443d96ecd2567441bea4efe762470eb61c2ba035fc60c60473088de62a'}
- P6: {'ran': True, 'reused_existing': True, 'exit': 0, 'sha256.dat': '82f47388984c3d3e3a754336d1485e947e122fcd4737fe3ff5750570fc72365e', 'sha256.sta': '74c6c10cff6c9e01e4d52378231d13e7d802919f26a7b779a4502308173e8b2d'}
- DYN: {'ran': True, 'reused_existing': True, 'exit': 0, 'sha256.dat': '8d2c98fa599abbec15449edc3ce9e224635f1fc676e7cc1be7717550943c1f3f', 'sha256.sta': '4ab47f724c0ad1289736843a05bbee326354a6ab8018c080fa63c9ab003deb6a'}

## 交接

找形层对上了可以写。六工况卡和恒载进风卡在。动力卡在。
建模岗到此交工况卡，不成稿。不成附件对照结论。
