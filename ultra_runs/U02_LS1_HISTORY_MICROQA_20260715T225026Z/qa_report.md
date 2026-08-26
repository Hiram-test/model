# U02 LS1 全历程能量微型验证

本作业只验证 B00/S10 将采用的 MAPDL 控制链，不代表任何全桥物理变体，也不把微型梁的稳定化能量比与任务书全桥阈值混用。

## 结论

- 状态：`PASSED`。
- MAPDL：ANSYS 2026 R1 / v261，串行 1 进程，返回码 0。
- OUT：WARNING 0、ERROR 0；ERR 仅 80 字节版本标识。
- LS1 固定 5 个子步，LS2 固定 1 个子步；RST 实际 6 个结果集。
- `SET,FIRST`/`SET,NEXT` 恰好导出 5 行 LS1，载荷步、子步和伪时间分别闭合为 `1 / 1..5 / 0.2..1.0`。
- 每行均成功执行 `ETABLE,SENE`、`ETABLE,STEN`、`SSUM` 与比值计算。
- CSV 在峰值门禁前显式 `*CFCLOS`，因此拒绝路径也能保留完整历程。
- 峰值为 `3.012752825741037`，位于 LS1 子步 1、伪时间 0.2；该大值来自刻意启用的微型验证稳定化设置，只用于证明峰值捕获，而非生产验收值。

## JSON 字段与固定值说明

- `schema_version=1`：本微型验证清单首版结构。
- `model_line=CONTROL_VERIFICATION`：只验证控制语法，不属于 LEGACY、DIAGNOSTIC 或 PRODUCTION 物理模型线。
- `processes=1`：小模型无需 DMP，避免并行文件干扰结果集遍历验证。
- `units=N-mm-s`：梁材料、几何、荷载和能量输出使用 N、mm、s；本算例没有质量项。
- `taskbook_threshold_applied_to_micro_model=false`：任务书 `1E-2` 是全桥硬门禁，本作业故意产生更高峰值以覆盖峰值捕获路径。
- `production_physics_claimed=false`：不得把本作业解释为 S10 或任何全桥变体通过。

## 六列 CSV

`hist.csv` 无标题，每行依次为：载荷步、子步、伪时间、SENE（N·mm）、STEN（N·mm）、`abs(STEN/SENE)`。无标题设计与全桥纯数值 APDL 输出保持一致，字段在本报告集中说明。

## 适用边界

该证据只关闭“MAPDL v261 是否支持并正确执行本次全历程遍历语法”的风险。未来全桥 S10 仍须从零完成 LS1、无稳定化 LS2 和预应力模态，并以自己的全历程 CSV 峰值 `<=1E-2` 为通过条件。
