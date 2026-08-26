# KEYOPT(5)=1 后 0.5% 迁移终止审计字段说明

`runtime_abort_audit.json` 为无注释 JSON，字段语义集中记录于此。力单位 N，力矩单位 N·mm，平移单位 mm，转角单位 rad。`ls1_converged=true` 仅证明 beta=1 旧荷载位置基态闭合。`ls2_completed_substeps=0` 表示 beta=0.995 首端点未收敛，中断时 ESAV、EMAT、R001 和 RST 均不得作为最终静力或模态状态。`single_difference_observed_effect` 表示相对默认 `KEYOPT(5)=0` 基准，前两轮 Newton 打印值没有变化，因此排除 rigid-beam 几何应力刚度未修复发散。下一轮只授权把 `NSUBST` 从 `200,200,200` 改为 `200,2000,200`，保留初始和最大增量 0.5%，允许求解器最小切回到 0.05%；不授权改变荷载、质量、连接、初始内力或四项收敛标准。
