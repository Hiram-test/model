# C10 单连接数值验证输入

这里有 3 个“柔性 BEAM188 master—单 TYPE72—双侧预拉 LINK180 slave—仅平移 MASS21”平移载荷案例、3 个 0.1 rad 单 TYPE72 有限转动案例和 6 个 ALL 六向载荷案例，共 12 份 APDL 输入。它们由 prepare 生成，但没有启动 MAPDL。生产候选只有 TYPE72，不含辅助节点、TYPE73、罚刚度或弱弹簧。

通过条件以 `qa/connection_unit_test_plan.json` 为准。除运动学与平衡外，日志必须满足 solver error=0、small/zero/negative pivot=0、自动 CNVTOL 重置=0，并且同一案例所有重组的方程数恒定。全桥启动仍需完成这些微模型、初始状态—外荷载路径复核和独立审查。
