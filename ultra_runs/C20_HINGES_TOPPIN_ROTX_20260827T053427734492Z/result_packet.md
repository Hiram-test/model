# C20 TOPPIN ROTX 结果包

- Run: `C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z`
- Job: `cw_C20x_0827t053427`
- Parent: `S10_SECTION_SHEAR_20260716T050342389124Z`
- 284 条立柱顶 CERIG `UX,UY,UZ,ROTY,ROTZ`（释放 ROTX）；底端 284 条 CERIG `ALL`

## 静力（G13 数值部分 PASS）

| 量 | 值 |
|---|---|
| LS1/LS2 CNVG | 1 / 1 |
| 质量 | 4108.466907580443 t（误差 4.43e-10 t） |
| UZ 支承 | 464 |
| FZ 反力相对误差 | 1.694e-12 |
| LS1 历程峰 \|STEN/SENE\| | 5.78e-33 |
| LS2 \|STEN/SENE\| | 2.66e-34 |
| UZ 支承 FSUM FX,FY,FZ | 0.717 N, 2.9e-5 N, −4.028762654e7 N |

## 模态

- Lanczos 80 阶：0.03682120–0.38670117 Hz（OUT）
- RSTP 仅展开 **51** 阶（2.20 GB vs SPRING 3.45 GB；STAT Mode=51）
- 紧凑 POST1 已导出 51 阶频率、50 阶 SENE、50 阶×11 测点振型

表 4-1 物理配对见 `qa/c20_table41_pairing.md`。TA1 物理落在 M3=0.07336 Hz（与 LA 杂交），不是按阶次把 M4 标成 TA1。第一阶扭转主导是 M6=0.10338 Hz（正对称）。门架 ROTX 局部簇从 0.223 Hz 起。

## G13

`PASS_WITH_BOUNDS`：网格加密未在本 deck 重跑；RSTP 52–80 未展开；官方 PFACT 未能从 MODE 文件读取；自由体切段未做。
