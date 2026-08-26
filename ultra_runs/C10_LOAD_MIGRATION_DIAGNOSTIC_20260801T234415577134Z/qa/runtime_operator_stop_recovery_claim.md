# C10 有效 nonlinear ABT 追加式恢复认领

旧工具 `ultra_c10_diagnostic_sufficiency_stop.py` 创建了零字节 ABT；该载荷不满足 MAPDL 非线性干净终止合同。旧控制器 PID `14676` 及包装器已退出，旧超时 final 摘要为 `6c35311d7e0133302c504e7c71906fb0a511ca99b890288ec14cf5c4b6c792d4`，旧 claim 摘要为 `72b99894cbc0a7b6e39e0971b8ac680c5a1ee41a19ffeeb893deae24874c8cb7`。

本恢复只针对 `C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T234415577134Z` / `cw_C10madp_0801t234415577134_d1`。在再次核对同一进程树、无硬事件、MNTR 至少两个 `5E-7` 接受步且剩余投影严格超过七天后，工具将排他创建 `cw_C10madp_0801t234415577134_d1.abt`，精确写入十字节 ASCII `nonlinear\n`；计划回执明确写在动作前，执行回执只在写入、flush、fsync 和读回一致后形成。工具绝不调用任何主动结束或强制结束进程的接口，部分结果禁止用于模态和生产。
