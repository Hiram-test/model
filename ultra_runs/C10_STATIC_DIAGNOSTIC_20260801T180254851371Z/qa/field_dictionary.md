# 静力诊断机器字段说明

JSON 不支持注释，因此字段语义集中记录于此。`STATIC_DIAGNOSTIC_PREPARED` 仅表示输入已生成且证据门通过，不表示 MAPDL 已启动。`SMP_SERIAL_NP1_DIAGNOSTIC_ONLY` 是低内存条件下的诊断例外，不替代正式 DMP4 运行。LS1 的 `KBC=1`、`AUTOTS=false`、`NSUBST=[1,1,1]` 表示完整初始索力与完整恒载在第一个平衡端点同时生效；LS2 保持相同外载并以一个子步检验零物理增量稳定性。`CNVTOL` 三项显式值禁止 MAPDL 自动放宽默认准则。`modal_requested=false` 表示本包主动截断全部模态命令。力单位为 N，长度为 mm，力矩为 N·mm，质量为 tonne，时间为 s。
