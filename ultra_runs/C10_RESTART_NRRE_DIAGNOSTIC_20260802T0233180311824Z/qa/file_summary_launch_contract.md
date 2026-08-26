# 重启帧清单读取执行合同

- 执行程序固定为 ANSYS MAPDL 2026 R1，二进制 SHA-256 为 `6c6327f6b906db8e6dd498bd38c97685d7e3e4acf52fccbf243b2dff7ed7af1b`。
- 只使用串行 SMP `-np 1`，避免把一次元数据读取误包装成分布式求解。
- 输入中不存在 `ANTYPE`、`SOLVE`、`SAVE`、删除或改名命令；唯一目的为 `RESCONTROL,FILE_SUMMARY`。
- 执行前六个输入工件已冻结在 `prepared_file_summary_hashes.sha256`；执行后必须复算复制重启文件未改变。
- 本动作不产生有效静力结果，模态与生产用途保持禁止。
