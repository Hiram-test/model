# S10 最终执行字段字典

## 状态

- `execution_status=EXECUTED`：DMP4 / INTELMPI 主作业已真实完成。
- `qa_status=PASSED_FOR_S10_SECTION_SHEAR_TRIAL`：本次 SEC61..66 剪切因果试算的数值与完整性门禁通过。
- `valid_for_s10_section_shear_trial=true`：结果可用于本次单变量试算判断。
- `valid_for_production_model=false`：S10 是因果变体，不自动替代生产模型。
- `next_action=NONE_FOR_THIS_RUN`：本 run 不需要再次启动。
- `pipeline_next_action=REBUILD_C10_FROM_FINAL_S10_BOUNDARY`：后续纯连接 C10 必须从本次最终边界重新准备。

## 数值单位

- 静力 SENE/STEN：N·mm。
- 质量：tonne。
- 反力和 LINK180 轴力：N。
- 频率：Hz。
- 有效质量比例、SENE 比例和误差比例：无量纲。

## 模态与向量

- `modal.property_rows=80`、`set_count=80`、`requested/available/exported=80` 共同证明 80 阶闭合。
- 两类向量各 80 份，每份含 91,407 个实际求解自由度节点。
- 拓扑节点与向量节点差 17,679，恰等于 TYPE70 第三方向节点数；这些方向节点没有独立求解自由度，不属于漏导出。
- 固定 80 阶合同没有设置 90% 累计有效质量硬门槛；实际 X/Y/Z 比例只作为范围限制报告。

## 六截面 SENE

- `s10_section_modal_sene.csv` 每行 16 列：阶次、全模型 SENE、SEC61..66 六组 SENE、六组占比、六组和、六组和占比。
- 总 SENE 必须正，分量 SENE 非负，比例在 `[0,1]`，三类恒等式误差不超过 `1E-12`。

## LINK180 POSTONLY

- S10 不能复用 A10 轴力结论；`S10_LINK180_POSTONLY_*/qa_summary.json` 直接读取 S10 的 LS2/time=1.001。
- 73,692 个 TYPE4 元素必须全部唯一且轴力严格为正。
- 平衡 DB 和静力 RST 在 POST1-only 前后以及 finalizer 当前时点的 SHA-256 必须一致。

## 谱系与账本

- prepare 根状态、manifest、结果说明、52 项 prepare 账本和 running 回执均原样归档到 `lineage/`。
- `solver/` 在 finalizer 中永久只读；二进制大小和 `mtime_ns` 在证据收集、写入和全账本哈希前后必须一致。
- `artifact_hashes.sha256` 覆盖 run 下除自身外全部普通文件，包括 solver 原生文件、160 份向量、LINK180 审计包、最终 QA、lineage 和编排器快照。
- 账本按设计排除自身，避免自引用悖论；`launch_command.txt` 仅作为 prepare-time 历史命令证据。

## 结论范围

- 报告原始全节点双精度模态向量不可得，严格 MAC 维持 `HARD_SOURCE_EVIDENCE_BLOCK`。
- 近重根模态跨模型比较必须采用子空间方法，不能按阶次强配。
