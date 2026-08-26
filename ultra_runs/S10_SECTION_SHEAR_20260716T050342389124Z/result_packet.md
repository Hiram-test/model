# S10 截面剪切单变量正式执行结果

- 最终状态：`PASS_WITH_LEGACY_LIMITATIONS`；QA：`PASSED_FOR_S10_SECTION_SHEAR_TRIAL`；最终化时间：`2026-07-16T09:27:34.092058+00:00`。
- MAPDL：DMP4 / INTELMPI 已真实完成；主 OUT 为 0 ERROR、0 FATAL、0 negative/zero pivot。
- warning：实际 5 条，摘要计 4 条且退出后追加 1 条性能 warning；全部已在 `qa/warning_disposition.md` 处置。
- 静力：LS1/LS2 均收敛；质量绝对误差 1.061380316969007e-09 tonne；反力相对误差 3.565689192148343e-11。
- LS1 全历程：20 个连续子步；峰值 `|STEN/SENE|=5.797346389239444e-33`。
- 模态：80 行属性、80 个 RSTP 结果集、80 份位移向量和 80 份转角向量；频率范围 0.03682163214586436–0.4122063826843537 Hz。
- 有效质量：80 阶累计 X/Y/Z 比例为 13.155935%/89.061423%/82.427858%；固定 80 阶合同未设置 90% 硬门槛。
- 六截面 SENE：80×16 表通过；六组元素合计 17,679，与 TYPE70 完全一致。
- LINK180：73692 个 TYPE4 全覆盖，非正轴力 0，最小轴力 519002.6875 N。
- 源完整性：LINK180 POST1-only 前后及 finalizer 当前时点的平衡 DB/RST SHA-256 一致。
- prepare 与 running 原件：状态、manifest、结果说明、52 项账本和启动回执已原样归档到 `lineage/`。
- 最终全 run 账本：`artifact_hashes.sha256` 覆盖除自身外全部普通文件。

## 适用范围和限制

1. S10 是 SEC61..66 截面剪切属性单变量因果试算，可用于本次试算判断，但不自动替代生产模型。
2. legacy 约束方程大变形 warning 与矩阵系数比超过 1E8 的尺度边界仍保留。
3. 最小相邻频差为 2.957037958661868e-06 Hz，对应 47–48 阶；跨模型比较必须采用近重根子空间方法。
4. 报告原始全节点双精度模态向量不可得，严格 MAC 和 14 目标一一物理映射维持硬源证阻断，不得按频率或阶次强配。

权威机器结论见 `qa/s10_external_completion_qa.json`；字段说明见 `qa/execution_field_dictionary.md`。
