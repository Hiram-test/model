# 不降阶全场训练的历史源文件

本目录保留按 SHA-256 命名的完整源代码快照，便于核对短窗口训练、完整历程训练和后续编排修改。它们保留了原始相对路径逻辑，复现历史版本时应在隔离工作副本中恢复到对应原文件名，再使用对应实验日志和 `contract.json` 记录的参数运行。不要直接从本目录启动快照，也不要覆盖正在计算的工作副本。

| 快照名称前缀 | 原文件位置 |
| --- | --- |
| `operator_short_windows_`、`operator_full_history_` | `automation/local_bridge_operator/complex_operator.py` |
| `operator_finalize_before_atomic_`、`operator_finalize_atomic_initial_` | `automation/local_bridge_operator/complex_operator_finalize.py` |
| `complex_operator_finalize_before_residual_recovery_` | `automation/local_bridge_operator/complex_operator_finalize.py` |
| `operator_costs_before_rebar_`、`operator_costs_rebar_adapter_` | `automation/local_bridge_operator/complex_operator_costs.py` |
| `complex_operator_export_before_residual_recovery_`、`complex_operator_export_before_memory_payload_` | `automation/local_bridge_operator/complex_operator_export.py` |
| `complex_operator_figures_before_label_spacing_` | `automation/local_bridge_operator/complex_operator_figures.py` |

最终摩擦和钢筋实验目录内还分别保留实际 `base_source.py`、`dynamic_source.py`、材料 wrapper 源码与 SHA 合同。后处理修复不更改它们的训练版本。原子导出和成本适配的源快照用于重放旧报告行为或核对修复；原始训练数据、权重和数值预测未据此改变。

当前完整场模型保留源有限元的节点、已输出积分点和明确界面实体。隐藏特征按每个实体保存；没有固定 POD 响应基、模态截断、粗化输出图或少数标量代替完整场。时间训练包含完整冷启动历程，按四步截断梯度以限制内存；预测状态和隐藏历史在段间继续传递。

直接状态输出与增量输出具有相同参数名称，不能据此混用加载器。直接状态检查点标记为 `architecture_variant=absolute_normalized_state`，由 `complex_operator_validation.load_absolute` 或 `complex_operator_finalize.load` 显式重建。最终结果还需在新的 Python 进程中运行 `complex_operator_replay.py`，比较完整保存预测并同时污染两个未来真值数组。

`complex_operator_dynamic.py` 的闭环是有明确轮数的计算任务：冻结候选排序、原生求解、质量隔离、完整场误差定位、继续训练、固定验证集选择及旧权重回滚。`round_complete.json` 可恢复完成的训练阶段；原生请求账本保留未完成或失败尝试，不会把它们当作正确标签。改变数据、算法或预算应使用新的实验目录。最终测试通过独立的 `complex_operator_finalize.py` 执行，不用于补样或模型选择。

主动和随机分支使用相同初始权重、合格数据目标及训练规则。两者可能请求同一原生参考解，因此记录的合格历史数量不代表新增求解次数，也不代表相同冷启动有限元耗时。原生参考解还必须单独满足网格和时间步检验；神经误差仅比较明确版本的离散参考场。
