# A0 机器字段说明

`STATIC_DIAGNOSTIC_PREPARED` 只表示 S10/C10 源哈希、当前 5,078 个 TYPE72、十一份依赖、A0 deck 和运行工具已通过准备门，不表示 MAPDL 已启动。LS1 严格使用 `KBC,0 / AUTOTS,ON / NSUBST,20,200,20 / PRED,OFF`；LS2 使用 `KBC,0 / AUTOTS,OFF / NSUBST,1,1,1`。本包唯一数值新增是 `NLDIAG,NRRE,ON,50`，没有 `CNVTOL`、`KEYOPT`、初始状态、质量、荷载、预测器或迭代上限变化。`DEFAULT_CNVTOL_DIAGNOSTIC_ONLY` 表示 A0 只回答“当前 TYPE72 在 S10 原始成功路径上能否重现静力”，监控器把 CNVTOL 被忽略或内部自动放宽消息列为硬事件；A0 即使通过也不得直接升格生产，必须再运行同一路径且恢复当前四项显式 CNVTOL 的 A0b 静力验收。主控在静力外部门前截断，绝不执行模态。单位为 N、mm、tonne、s。
