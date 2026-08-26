# 最小增量残差运行顺序

当前包只完成准备，ANSYS 未启动。确认没有任何 MAPDL/MPI 运行后，先执行 `execute_via_frozen_launcher.txt` 中的唯一命令；启动器返回 PID 和 `RUNNING_MINSTEP_NRRE_IDENTITY_CAPTURED` 后，立即在另一进程执行 `monitor_via_frozen_monitor.txt`。不得直接执行底层 `launch_command_smp1.txt` 绕过准备账本、资源门和进程身份。监控器无强制结束路径；无硬事件时等待自然完成，有冻结硬事件时只写官方 `nonlinear\n` ABT 并继续等待自然退出。完成后必须独立终结并哈希 DB、RST、NRxxx、OUT、ERR、MNTR 和重启动文件；在此之前不得发布任何静力或模态结论。
