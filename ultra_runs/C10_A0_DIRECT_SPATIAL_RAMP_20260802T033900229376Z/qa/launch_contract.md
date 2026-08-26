# A0 启动与监控合同

当前状态：准备完成、ANSYS 未启动。

只读复核：`python -B input_snapshot/ultra_c10_a0_execute.py --run-dir <本运行绝对目录> --validate-only`。该命令不得生成任何 runtime 或 solver 输出。

若后续另行明确授权实际启动，才使用同一冻结脚本的 `--launch`，并立即以 `python -B input_snapshot/ultra_c10_a0_monitor.py --run-dir <本运行绝对目录>` 附着。启动器只允许 SMP1、唯一 job、无并发 MAPDL、足够内存和磁盘；监控器只允许官方十字节 `nonlinear\n` ABT，不调用 terminate、kill 或信号接口。
