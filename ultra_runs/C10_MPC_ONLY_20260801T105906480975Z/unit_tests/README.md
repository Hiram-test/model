# C10 单连接数值验证输入

这里有 5 档罚因子 × 6 个单位力/力矩，共 30 份 APDL 输入。它们由 prepare 生成，但没有启动 MAPDL。UXYZ 的三个释放转角用 1 N·mm/rad 的 COMBIN14 弱弹簧稳定；后处理时必须把弱弹簧反力与 joint 传力分开，不得把该稳定项当成真实连接刚度。

通过条件以 `qa/connection_unit_test_plan.json` 为准。全桥启动仍需完成这些微模型、数值秩/主元审计和独立复核。
