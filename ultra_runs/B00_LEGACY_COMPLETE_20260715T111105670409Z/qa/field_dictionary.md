# B00 字段字典

本文件解释同一 run 内 JSON、SHA-256、TXT 与 CSV 机器文件。JSON 和 CSV 语法本身不支持注释，因此字段含义、单位和门槛集中记录在这里。

## manifest.json 与 B00_status.json

- schema_version：整数 1 表示首版 B00 prepare-only 契约。
- run_id：固定 B00_LEGACY_COMPLETE，也是不可覆盖目录前缀。
- model_line：固定 LEGACY，表示 CERIG 5078 冻结模型线。
- status：固定 PREPARED_NOT_STARTED；不表示 MAPDL 已启动或结果有效。
- next_action：固定 B00_PREFLIGHT_MEMORY_AND_INDEPENDENT_AUDIT_REQUIRED。
- created_utc：准备动作的 UTC ISO-8601 时间，含微秒。
- run_dir_name：B00_LEGACY_COMPLETE 加 UTC 微秒时间戳的目录名。
- jobname：唯一 ASCII MAPDL 前缀，格式 cw_B00_MMDDtHHMMSS_xx，长度不超过 28。
- parent_u00 / parent_u01：固定 U00 与用户显式指定且通过 8/8 的 U01 lineage。
- modes_requested：Block Lanczos 请求阶数；不小于 80 且为 40 的倍数。
- upper_frequency_hz：频率搜索上限，固定 0.35 Hz。
- prepare_only：固定 true；mapdl_execution_attempted、mapdl_started、process_started、execution_attempted 均固定 false。
- memory_snapshot：准备瞬间 Windows 物理内存；容量字段单位 byte，布尔门禁不触发执行。
- disk_snapshot：项目所在卷实时容量；minimum_free_bytes_for_execution 固定 32 GiB。
- dependencies：U00 图 order 1 至 11 的绝对源、basename、图哈希、input_snapshot 和 solver 复制件。
- topology_expectations：未来装配后的节点、单元及 TYPE 4、6、70、71 硬门禁。
- static_solution_contract：LS1、LS2、能量、质量、支承和反力门槛；两步 stabilization 均为 OFF。
- modal_solution_contract：扰动重启动、Lanczos、MXPAND 与导出协议。
- execution_qa_required：运行后仍需人工或独立程序完成的检查，包括 LINK180 非正轴力审查。
- future_launch.argv：只记录未来 DMP4 参数，不是已执行进程。

## qa/preflight.json

- prepare_gate_passed：U00、U01、源图、哈希、命令计数、审计与复制闭合全部通过后为 true。
- checks：准备期硬门禁列表；每项含 check_id、passed、actual 和 expected。
- u00_source_ledger_entry_count：从磁盘复算通过的 U00 source 账本行数。
- u01_source_ledger_entry_count：复算通过的显式 U01 source 账本行数。
- u01_artifact_ledger_entry_count：U01 artifact 账本覆盖文件数；账本自身因自引用悖论排除。
- resource_gate_is_nonexecuting：固定 true，说明资源真假都不会由本脚本启动 MAPDL。
- memory_ready：可用物理内存是否至少 8 GiB。
- disk_ready：项目所在 D 盘可用空间是否至少 32 GiB。

## b00_modal_properties.csv

该文件没有标题行，避免 APDL 字符串写出差异。每个实际存在的模态一行，共 15 列：

1. mode：一基模态序号，整数。
2. freq_hz：官方 MODE/FREQ 频率，单位 Hz，文本精度 E24.16。
3. genm：官方 MODE/GENM generalized mass。
4 至 9. pfact_x、pfact_y、pfact_z、pfact_rotx、pfact_roty、pfact_rotz：六方向 participation factor。
10 至 15. effm_x、effm_y、effm_z、effm_rotx、effm_roty、effm_rotz：六方向 effective mass。

六方向 PFACT/EFFM 使用 v261 已验证的 MODE、PFACT 或 EFFM、DIREC、方向参数序列。本输入不使用不存在的 PRMASS 命令。

## 其他求解器文本

- b00_topology_counts.txt：NODE、ELEMENT、TYPE4、TYPE6、TYPE70、TYPE71 装配计数。
- b00_constraint_equations.txt：原生 CELIST,ALL 约束方程审计。
- b00_coupled_dof.txt：原生 CPLIST,ALL，执行后与准备期 12 条 CP 闭合。
- b00_displacement_constraints.txt：原生 DLIST,ALL，执行后与准备期 3968 条 D 闭合。
- b00_static_energy_mass_reaction.txt：两步 CNVG、SENE/STEN 比、总质量、UZ 支承和反力闭合。
- b00_modal_export_manifest.txt：requested、available、exported 三项阶数。
- b00_modal_set_list.txt：RSTP 原生 SET,LIST。
- mode_XX_all_nodes.txt：第 XX 阶 PRNSOL,U,COMP 全节点位移。
- mode_XX_rotations.txt：第 XX 阶 PRNSOL,ROT,COMP 全节点转角。
- jobname.out：未来 MAPDL 主输出；prepare 阶段不存在，执行后必须检查 ERROR、WARNING 和完成状态。

## SHA-256 账本

- source_hashes.sha256：源路径和关键复制件摘要；格式为 64 位摘要、两个空格、标签。
- artifact_hashes.sha256：run 内除该账本自身外的全部文件；排除自身是避免自引用哈希悖论。
