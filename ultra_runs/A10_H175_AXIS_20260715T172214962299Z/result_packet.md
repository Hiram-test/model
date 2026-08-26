# A10 H175 局部轴正式执行结果

- 最终状态：`PASS_WITH_LEGACY_LIMITATIONS`；执行状态：`EXECUTED`；最终化时间：`2026-07-15T22:55:59.378708+00:00`。
- MAPDL：DMP4 / INTELMPI 已真实完成；主 OUT 为 0 ERROR、0 negative pivot、0 zero pivot。
- warning：实际 5 条，摘要计 4 条且退出后追加 1 条性能 warning；五条均已在 `qa/warning_disposition.md` 逐项处置。
- 静力：LS1/LS2 均收敛；LS2 时间=1.001；质量绝对误差=1.061380316969007e-09 tonne；反力相对误差=1.907675526569801e-11。
- STEN：两次 `STABILIZE,OFF` 分别在 LS1/LS2 `SOLVE` 前生效且 OUT 各回显一次 KEY=OFF；端点 STEN/SENE 分别为 2.667479851077623e-34 和 2.667479843364189e-34，任务书全历程控制门禁通过。
- 模态：80 行属性、80 份位移向量、80 份转角向量；频率范围 0.03682163352861133–0.4122076645938122 Hz；第 59 阶已越过 0.35 Hz。
- 六组件 SENE：80 行总能量和 480 行组件长表通过；六组件并集与 TYPE70 均为 17679；全部 80 阶原始能量保留，供后续 14 目标模态按物理描述/MAC 映射，不作按阶号硬配。
- LINK180：73692 个 TYPE4 全覆盖，非正轴力数=0，最小轴力=519006.875 N。
- 源完整性：当前时点重新计算平衡 DB、静力 RST、模态 DB 与 RSTP 四个 SHA-256，均与两个 POSTONLY 运行前后共同记录一致；两个正式 OUT/ERR 均为 0 warning、0 error 并 NOSAVE。
- prepare 原件：根 `A10_status.json` 与 `manifest.json` 的原始字节已归档到 `lineage/`，根文件已更新为真实终态。
- 全 run 哈希：`artifact_hashes.sha256` 覆盖除自身外全部普通文件，包含 solver 二进制、正式 QA、lineage 与 rejected 尝试。

## 保留边界

1. legacy CERIG 大变形兼容性 warning 仍存在。
2. 矩阵系数比超过 1E8，虽无负/零主元且结果收敛，仍保留尺度病态限制。
3. LS1/LS2 全历程稳定化关闭已有控制证据，但 RST 只保存端点 VENG，逐子步 STEN 数值表不可由 POST1 恢复。

权威机器结论见 `qa/a10_external_completion_qa.json`（与 `qa/postrun_gate.json` 逐字节一致）；字段解释见 `qa/execution_field_dictionary.md`。
