# C10 TYPE72 KEYOPT(5)=1 迁移诊断终止结果

状态：`ABORTED_BY_CONTROLLER_AFTER_LS2_FIRST_0_5_PERCENT_MIGRATION_DIVERGED_WITH_MPC184_STATIC_STRESS_STIFFNESS_EXCLUDED`。

- LS1 在 4 次迭代收敛：力残差 0.7009 N，力矩残差 10.78 N·mm，最小正主元 25.3126539。
- LS2 首个 0.5% 端点未收敛：第 1/2 轮力残差为 522.4 N / 85.00 MN，力矩残差为 10.78 N·mm / 1.515 GN·mm，位移修正为 -0.8899 mm / -12.17 mm。
- 上述 LS2 打印轨迹与默认 KEYOPT(5)=0 基准相同，因此关闭 TYPE72 rigid-beam 几何应力刚度没有修复发散。
- 控制器已核对并停止包装 PID 46496 与实际求解 PID 15788；两者均已消失。
- 没有取得有效静力端点，没有执行模态，也不允许生产使用。
- 下一轮唯一获准变化为 `NSUBST,200,2000,200`，允许 0.5% 首步失败时切回至最小 0.05%。
