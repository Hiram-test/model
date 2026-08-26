# A10 最终执行字段字典

## 状态字段

- `execution_status=EXECUTED`：MAPDL 主作业已经由 prepare 之外的外部命令真实运行完成。
- `gate_status=PASSED`：本脚本要求的全部 post-run 硬门禁均通过。
- `status=PASS_WITH_LEGACY_LIMITATIONS`：数值门禁通过，但仍保留 legacy CERIG 大变形、矩阵尺度病态和逐子步 STEN 数值未保存三项边界。
- `next_action=NONE_FINALIZED`：当前 run 已最终封板，不再等待 launch。
- `qa/a10_external_completion_qa.json`：供 A30 与后续任务复用的权威入口；与 `qa/postrun_gate.json` 逐字节一致。

## 数值字段

- `static.*_n_mm`：势能或稳定化能，单位 N·mm。
- `static.mass_*_tonne`：质量与绝对误差，单位 tonne。
- `static.reaction_*_n`：重力反力，单位 N；`reaction_relative_error` 无量纲。
- `modal.frequency_*_hz`：频率，单位 Hz；第 59 阶首次超过 0.35 Hz 是频带未截断的直接证据。
- `modal.displacement_vectors.count` 与 `rotation_vectors.count`：两类 PRNSOL 文件均必须为 80。
- `sene6`：六组件正式只读 QA；80 行总能量、480 行组件长表、比例闭区间 0–1。
- `sene6.energy_scope`：任务书有 14 个目标物理模态，但禁止按阶号硬配；A10 保留 80×6 原始能量供后续 MAC/物理描述映射，因此 `hard_order_target_pairing_claimed=false`。
- `link180.actual_count=73692` 与 `nonpositive_count=0`：LS2 LINK180 TYPE4 全覆盖且全部正拉力。

## 证据与账本

- `source_integrity`：当前时点重新计算平衡 DB、静力 RST、模态 DB 和 RSTP 四个大文件的 SHA-256，并与两个 POSTONLY 的运行前后共同记录逐项比较。
- `postonly_execution`：直接读取两个正式 OUT/ERR；均须 0 warning、0 error、80 字节版本 ERR 且 `EXIT ... WITHOUT SAVING DATABASE`。
- `prepare_lineage` 指向 prepare 根状态和 manifest 的原始字节副本；其 SHA-256 与最终化前根文件相同。
- `artifact_hashes.sha256` 递归覆盖 run 下全部其他普通文件，包括 solver 二进制、正式 QA、lineage 与 rejected 尝试；账本按设计排除自身，避免自引用。
- `solver_binary_metadata_unchanged=true` 表示 finalizer 写入前后所有受保护 solver 二进制的字节数与纳秒修改时间完全一致；账本另给出其内容 SHA-256。
- `sten_control.taskbook_full_history_peak_gate_status=PASSED_BY_DISABLED_STABILIZATION_CONTROL`：两次 `STABILIZE,OFF` 在各自静力 `SOLVE` 前生效且 OUT 各回显一次 `KEY=OFF`，故 LS1/LS2 全历程未启用人工稳定化。
- `sten_control.full_substep_numeric_history_available=false` 是证据能力边界，不是门禁失败；RST 未保存的逐子步数值不得由端点伪造。
