# C10 自适应迁移诊断充分性受控停止封存

最终状态：`STATIC_DIAGNOSTIC_SUFFICIENCY_CONTROLLED_STOPPED_BEFORE_BETA_ZERO`。这不是 beta=0 静力完成，也不是模态结果；它只证明继续计算的诊断价值已经不足，并由有效 MAPDL `nonlinear` ABT 干净停止。

- 准备与执行身份：准备账本 29 项全部复算通过；manifest、主控输入、MAPDL 2026 R1 二进制、启动 claim/launch/identity 和 SMP1 命令行一致，原 job 进程树已全部退出。
- 旧事故：旧工具排他创建的是零字节 ABT，MAPDL 消费后没有退出；旧控制器等待 1802.3 秒超时并明确未调用 terminate/kill。旧工件全部保留，未覆盖。
- 有效恢复：恢复工具排他创建十字节 `nonlinear\n`，SHA-256 为 `efc0d415f2fa6a5bea29d619ed2c58fb6ee8285e68bf671673dc2c56e43f8703`；完整写入、flush/fsync、同句柄回读均通过，ABT 被 MAPDL 消费，OUT/ERR 在旧超时前缀之后出现原生终止确认，进程树和 lock 自然消失。
- 持续监控：最终 JSONL 共 926 个连续样本；硬事件 0，监控器自身中止请求 0，terminate/kill PID 均为空，OUT/ERR/MNTR 与 monitor/recovery final 快照一致。
- 数值健康：全部方程报告均为 1,234,834；1 个最小主元均有限且为正，最小值 25.3126539；未见 FATAL、small/zero/negative pivot 或 CNVTOL 被忽略/重置。
- 充分性：MNTR 只有 LS1 和恰好两个 LS2 接受步；两个 LS2 增量均为 `5E-7`，后一步 Newton 迭代 45 次，实测每最小步 2872.300 秒，剩余 1998 个最小步投影 5738855.400 秒（66.422 天），严格超过七天。
- 工程结论：beta=0 未达到，静力端点不存在，`valid_static_result_obtained=false`。任何部分 RST、DB、RDB、LDHI 或重启动碎片都不得作为本项目重启动基态、预应力模态基态、设计验算或生产结果。模态状态为 `BLOCKED_NOT_RUN`，`modal_execution_allowed=false`，`production_claim_allowed=false`。

机器审计见 `qa/diagnostic_sufficiency_stop_audit.json`，非自引用全运行追加账本见 `artifact_hashes_diagnostic_sufficiency_final.sha256`。
