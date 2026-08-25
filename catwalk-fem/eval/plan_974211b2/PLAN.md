# 974211b2 实验方案（#19 可读路径）

路径：`catwalk-fem/eval/plan_974211b2/`。这是当前**执行**方案（扒线形、叠预应力、回读主 deck），不是 STEP 历史稿，不是 demo-rl-calculix。

预注册（H-ZJG-CCX-OF-001）：`docs/catwalk-experiment-plan-ccx-operating-force/`。对照对象同样是 CCX 运营力；703.46 不得当论文结果。本目录把线形叠层做完并回读 `974211b2`。

对照对象是 **CalculiX 自己的运营力**（主 deck 上已叠的预应力，以及线性步由 S 反算的轴力）。线形按 MCT 扒完再叠。主不换。

## 1. 对象（已定）

| 角色 | 路径 | SHA-256 | 处置 |
|---|---|---|---|
| 主 deck | `catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp` | `974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1` | 不换主，不改写 |
| 线形 / 预应力源 | `catwalk-fem/mct-from-zero/source/01_设计资料与规范/猫道 - 门架索合建模型2.mct` | `0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1` | 图纸没有就从这里扒 |
| 冻结 cleared | `catwalk-fem/artifacts/zjg_catwalk_cleared.inp` | `760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9` | 不动 |
| S10 `.db` | Release `catwalk-attachment23-v2.0-s10-20260716` | `17e0bac8…` | 抽不出索力，表保持 null |
| 附件 2-3 | 抗风报告频率 / 表 5-3、5-4 | — | 本方案不写符合 |

主 deck 与 `mct-from-zero/artifacts/mct_from_zero_static.ccx.inp` 字节相同。1125 节点，1123 T3D2，71 B31，IC 1123 eid × 8 IP。

## 2. 方法（已定，按此执行）

1. **线形图纸。** 本树没有《图纸汇总-2026.08.05.pdf》、没有猫道线形 DWG/DXF。扎青 DWG 不是本桥。线形只从 MCT `*NODE` / `*ELEMENT` / `*GROUP` 扒。
2. **扒。** 面层四跨组：北边跨、主跨、南边跨、南辅跨。门架索四跨组同名。Y 数值为 0，单线二维等效。
3. **叠。** 每根 TENSTR：`F` = `*INI-EFORCE` mean(i,j)，否则 `*INIFORCE` AXIAL；`A` 来自 MCT `*SECTION`；`σ = F/A`；`PK2 = σ n⊗n`，`n` 是 MCT 两端节点向量。71 根 TRUSS 门架无 INIFORCE，不编。
4. **主。** 叠层结果已经写在 `974211b2`。本方案只回读，不另写一张主。
5. **运营力对照。** 对的是 CalculiX 自己的预应力 / 线性步轴力，不是 ANSYS POST1，不是附件 2-3 成桥表。
6. **过门。** 线性步若是机构型、FRD DISP 节点 0、S≈IC，则记为不是平衡，不锁稿。

复跑：

```
python3 catwalk-fem/eval/plan_974211b2/overlay.py
python3 catwalk-fem/tests/test_plan_974211b2_overlay.py
sha256sum catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp
sha256sum catwalk-fem/artifacts/zjg_catwalk_cleared.inp
```

## 3. 本轮已执行的叠层

独立复算见 `alignment.json`、`overlay.json`、`geometry_overlay_report.json`、`OVERLAY.md`、`EVIDENCE.json`。1125 节点同源：残差 max 0.034 mm，是主 deck `.8g` 印刷圆整，不是第二套线形。

面层线形（MCT 组，单位 m）：

| 组 | L | z_left | z_right | z_min | sag | TENSTR |
|---|---:|---:|---:|---:|---:|---:|
| 北边跨 | 648.112 | 59.283 | 340.596 | 59.283 | 140.657 | 149 |
| 主跨 | 2302.000 | 340.596 | 340.598 | 113.300 | 227.297 | 295 |
| 南边跨 | 725.276 | 340.598 | 126.750 | 126.750 | 106.924 | 160 |
| 南辅跨 | 496.908 | 126.750 | 46.282 | 46.282 | 40.234 | 115 |

垂点组：nid 160 (1553.3, 334.645)、302 (2686.0, 113.300)、444 (3818.7, 334.537)。横向通道节点 21，门架 71。

预应力叠回主 deck：1123 / 1123 eid，PK2 对 ip1 max \|rel\| = 4.758×10⁻⁷。公式闭合，主未改。

## 4. 计算组已认（线性静力，不锁稿）

来源：计算组 + 本分支已有 `eval/ccx_mct_from_zero/ccx_run.json`（与 974211b2 同一 deck）。本 VM 无 `ccx`，本轮不重跑求解器。

| 项 | 认定 |
|---|---|
| 型 | 机构型。线性 T3D2 无几何刚度 |
| FRD DISP | 节点计数 0 |
| `.dat` U | 1125 点；\|U\|_max = 9.264×10⁹ mm |
| 应力 | S≈IC，不是平衡 |
| 轴力对 MCT INI-EFORCE | n=1123，p50=0.554%，最差 eid 1169，\|rel\|=0.19061214708677（−19.1%） |
| `balanced` | false |
| 703.46 MPa | 只是 eid 1 的 `F/A`（15686.25 kN / 22298.69165 mm² = 703.46055 N/mm²）。源侧恒等式。**不锁稿。** |

Job finished、方程可分解、S 贴近 IC，都不是索力平衡。

## 5. 下一步（只许副本，不许写回主）

1. 主保持 `974211b2`。对照表只从已登记四件套出。
2. 要几何刚度 / `*NLGEOM`，只开副本。已有 NLGEOM 副本第一增量 `1U`、exit 201，不写回主。
3. 位移场当形成桥静力之前，\|U\|_max 必须远小于主跨垂度 227.297 m。
4. 不写符合附件 2-3。不把 703.46 写进论文结论。
5. 不 push `main`。不开新 PR。不合并。不扭到 demo-rl-calculix。

## 6. 明确不做

- 不改 `974211b2`，不改 `760c0ee4`，不改 82548e6a / 41fb3222 / c635dad7。
- 不编 S10 LINK180 索力表。
- 不把 MCT 单线二维等效当成双幅 S10 网格。
- 不把 STEP 历史方案（`catwalk-fem/PLAN.md` 下文）当成当前执行对象。
