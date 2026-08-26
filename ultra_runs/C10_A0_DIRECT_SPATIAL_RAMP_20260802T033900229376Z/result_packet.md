# C10 A0 直接空间重力斜坡短验证准备结果

状态：`STATIC_DIAGNOSTIC_PREPARED`；ANSYS 未启动。

- 运行：`C10_A0_DIRECT_SPATIAL_RAMP_20260802T033900229376Z`；job：`cw_C10a0_0802t033900229376_d1`。
- 当前连接：5,078 个单层 TYPE72，`KEYOPT(1/2/5)=1/0/0`；辅助节点=0，TYPE73=0。
- 荷载路径：恢复 S10 的直接空间 MASS21 重力斜坡；LS1 为 `KBC,0 / AUTOTS,ON / NSUBST,20,200,20 / PRED,OFF`，LS2 为零增量保持。
- 唯一新增诊断：`NLDIAG,NRRE,ON,50`；未增加或修改 CNVTOL、KEYOPT、初始状态、质量、荷载、PRED 或 NEQIT。
- 收敛用途：`DEFAULT_CNVTOL_DIAGNOSTIC_ONLY`；日志中 CNVTOL 被忽略或内部自动放宽属于硬事件。A0 即使通过也不得直接升格正式修复，必须再做同路径且恢复当前四项显式 CNVTOL 的 A0b 静力验收。
- 分析范围：装配、两步静力和全部静力门；模态命令已完整截断。
- 当前没有静力结果、模态结果或生产结论。A0 若通过，先做 A0b 而不做荷载位置迁移；A0 若失败，才进入分组件迁移定位。
