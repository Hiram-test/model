# S10 运行状态说明

- `schema_version=1`：本运行记录采用第一版字段结构。
- `run_name` 与 `jobname`：分别标识独立 S10 目录和 MAPDL 作业名，禁止与其他运行复用。
- `started_at_utc`：MAPDL 主进程创建前记录的 UTC 时间。
- `main_pid=26176`：Windows 上的 MAPDL 启动进程 PID，仅用于本次运行监控。
- `parallel_mode=DMP`、`process_count=4`、`mpi=INTELMPI`：按封板命令使用四进程 Intel MPI 分布式并行。
- `memory_gate_overridden_by_user=true`：沿用用户已明确给出的内存门禁覆盖；不表示自然满足 8 GiB 可用物理内存。
- `disk_gate_passed=true`：启动前 D 盘可用空间超过任务书规定的 32 GiB 门槛。
- `status=RUNNING_UNFINALIZED`：只证明进程已创建，不代表静力收敛、80 阶完成、QA 通过或可用于工程结论。
- `artifact_ledger_pending_finalization=true`：运行态新增文件尚未纳入 prepare-only 账本；只有求解结束并完成外部 QA 后才会重建最终账本。
