# C20 当前有效作业

已完成静力+Lanczos 80 阶+紧凑 POST1 配对：

`C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z`  job `cw_C20x_0827t053427`

- 284 条立柱顶 CERIG `UX,UY,UZ,ROTY,ROTZ`（释放 ROTX）；底端抱箍 ALL
- 静力 LS1/LS2 CNVG=1，质量 4108.47 t（误差 4.4e-10 t），FZ 相对误差 1.7e-12
- Lanczos 80 阶 0.03682–0.38670 Hz；RSTP 展开到第 51 阶后中断
- 表 4-1 物理配对见该 run 的 `qa/c20_table41_pairing.md`
- G13 = PASS_WITH_BOUNDS（见 `qa/n15/`）

旧 SPRING 铰轴是 ROTY，不能再当 C20 生产父线。D10 必须从本 TOPPIN ROTX 重跑。
