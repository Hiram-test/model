# 5% 迁移运行终止审计字段说明

`runtime_abort_audit.json` 是 JSON，格式本身不允许注释，因此字段含义集中记录于本文件。力单位为 N，力矩单位为 N·mm，平移修正单位为 mm，转角为无量纲弧度。`ls1_converged=true` 只表示 beta=1 旧荷载位置基态闭合，不表示 beta=0 最终空间质量状态或完整静力通过。`ls2_completed_substeps=0` 表示首个 beta=0.95 端点尚未收敛，不能使用中断时的 ESAV、OSAV、RST 或结果帧作最终状态。`minimum_positive_pivot` 与恒定方程数证明本次失败不是旧双层约束病态复发。`next_migration_fraction=0.005` 表示新运行首段只迁移 0.5% 的荷载位置，其他物理量、拓扑和收敛标准不变。
