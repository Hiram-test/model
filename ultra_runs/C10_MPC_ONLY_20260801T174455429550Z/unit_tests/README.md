# C10 单连接数值验证输入

这里有 6 个 UXYZ 六向荷载、3 个 0.1 rad 有限转动和 6 个 ALL 六向荷载，共 15 份 APDL 输入。它们由 prepare 生成，但没有启动 MAPDL。UXYZ 荷载测试的三个 1 N·mm/rad COMBIN14 只用于稳定并量测释放转角，其反力必须单独报告；生产连接本身完全由 TYPE72 与 TYPE73 直接消元实施，不含罚刚度。

通过条件以 `qa/connection_unit_test_plan.json` 为准。全桥启动仍需完成这些微模型、直接消元链装配秩、初始状态—外荷载路径复核和独立审查。
