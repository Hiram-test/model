# A0 启动与监控合同

当前状态：准备完成、ANSYS 未启动。

只读复核：`python -B input_snapshot/ultra_c10_a0_execute.py --run-dir <本运行绝对目录> --validate-only`。该命令不得生成任何 runtime 或 solver 输出。

若后续另行明确授权实际启动，只使用同一冻结启动器的 `--launch`；启动器会在租约前后执行两次 MAPDL/MPI 空扫描、取得唯一全局主机租约、启动 MAPDL、自动启动冻结专用监控器，并在 30 秒内等待有效 claim，禁止人工另行附着。启动后任何非本 job MAPDL/MPI 都是硬事件，只允许向本 A0 job 写精确十字节 `nonlinear\n` ABT 并等待自然退出；绝不 terminate、kill、发信号或处置其他进程。启动器只允许 SMP1、唯一 job、至少四 GiB 可用物理内存和至少 24 GiB 空盘；磁盘门来自历史最大 C10 失败/NRRE 包 5.630 GiB 的约 4.26 倍。只有本 job 进程为空、lock 消失且 OUT/ERR/MNTR 连续稳定才释放租约；阻断或十分钟未闭合时保留租约供人工审计并阻止后继运行。
