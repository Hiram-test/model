# U01 机器文件字段说明

- `manifest.json`：套件身份、U00 父级、MAPDL 哈希、编排脚本哈希、内存快照和八个案例清单。
- `orchestrator_snapshot/ultra_u01_suite.py`：本 run 实际生成与判门逻辑的逐字节快照；其 SHA-256 同时写入根 manifest 与 `source_hashes.sha256`。
- `solver/<case>/manifest.json`：单案例 `/FILNAME`、并行模式、输入哈希、预注册结果和运行状态。
- `U01_status.json`：八项任务书测试的最终布尔门禁与全部关键指标；U01_03 的 `pair_results` 含六类乘两方向共十二对原生/ASEC 完整响应。
- `qa/U01_gate_results.csv`：`test_id` 为稳定测试编号，`passed` 为最终布尔值，`summary_json` 为该项完整指标。
- `sections__u01_section_properties.csv`：六行十三列依次为截面序号，原生 A、Iyy、Izz、J、SCyy、SCzz，以及 ASEC 的同六项属性；面积单位 mm^2，惯性矩与扭转常数单位 mm^4，剪切因子无量纲。
- `sections__u01_section_deflections.csv`：六行七列依次为截面序号，ASEC 全局 Y 数值/解析总挠度/相对差，ASEC 全局 Z 数值/解析总挠度/相对差；挠度单位 mm，相对差无量纲。
- `sections__u01_section_native_deflections.csv`：六行十四列依次为截面序号，ASEC/原生 Y 总挠度/相对差、分别扣弯后 Y 剪切挠度/相对差，ASEC/原生 Z 总挠度/相对差、分别扣弯后 Z 剪切挠度/相对差，以及方向映射码；映射码 1 仅表示 H175 原生截面绕梁轴旋转 90 度，0 表示两者 K 均指向 +Z。
- `sections__u01_section_torsion_audit.csv`：六行九列依次为截面序号，ASEC Y 工况 ROTX/MX，ASEC Z 工况 ROTX/MX，原生 Y 工况 ROTX/MX，原生 Z 工况 ROTX/MX；转角单位 rad，根部力矩单位 N·mm。
- `revolute_6dof__u01_revolute_6dof_result.csv`：六行五列依次为工况号、节点关节相对运动、载荷端响应、等效刚度、MPC184 自由 X 轴寄生约束力矩；平动单位为 mm 或 N/mm，转动单位为 rad 或 N·mm/rad，力矩单位为 N·mm。
- `revolute_6dof__u01_revolute_joint_result.csv`：六行九列依次为工况号、JFX、JFY、JFZ、JMX、JMY、JMZ、JRP4、JRU4；约束力单位为 N，约束力矩单位为 N·mm，相对位置与相对转动单位为 rad。
- `source_hashes.sha256`：编排脚本快照、输入快照及 run 外只读来源的 SHA-256；`SOURCE::` 后为来源绝对路径。
- `artifact_hashes.sha256`：本次 run 内全部交付文件的最终 SHA-256，不包含该清单自身。
- 各 APDL CSV 均无表头，因为字段说明由本文件和 `result_packet.md` 承担，未向不支持注释的格式插入非法注释。
