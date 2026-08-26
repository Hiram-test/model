# 0.5% 迁移运行终止审计字段说明

`runtime_abort_audit.json` 是 JSON，格式本身不允许注释，因此字段含义集中记录于本文件。力单位为 N，力矩单位为 N·mm，平移修正单位为 mm，转角单位为 rad。`ls1_converged=true` 只表示 beta=1 旧荷载位置基态闭合，不表示 beta=0 最终空间质量状态或完整静力通过。`ls2_completed_substeps=0` 表示首个 beta=0.995 端点尚未收敛，不能使用中断时的 ESAV、EMAT、OSAV、RST 或结果帧作为最终状态。`minimum_positive_pivot` 与恒定方程数证明本次失败不是旧双层约束病态复发。`next_diagnostic_single_difference` 只授权检查 MPC184 rigid-beam 几何应力刚度对 Newton 切线的影响，不授权改变荷载、质量、连接数量、直接消元运动学或收敛标准。
