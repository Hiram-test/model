# C10 单层 TYPE72 微算例验收

状态：`MICRO_VALIDATION_PASSED_FULL_BRIDGE_NOT_RUN`。

- prepare：`C10_MPC_ONLY_20260801T190630474559Z`
- execution：`C10_MICRO_VALIDATION_20260801T190634755506Z`
- 真实运行：12/12；通过：12；失败：0。
- 生产候选与 UXYZ 微测均为一条 TYPE72；辅助节点=0、TYPE73=0、罚刚度参数=`null`。
- 三个受矩有限转动案例各有 1 个独立方程；三个生产拓扑 UXYZ 各有 18 个；六个 ALL 各有 12 个，案例内均恒定。
- 本工件只关闭单连接运动学、装配秩警戒和六向传力门禁；全桥静力、初始状态路径和模态仍为 `NOT_RUN`。

## 数值控制值

- 最大生产拓扑刚体平移误差：5.456968e-12 mm。
- 最大有限转动 Rodrigues 位移误差：2.273737e-13 mm。
- 最大 solver-only 代数转角差：0.000000e+00 rad。
- 最大全局力平衡残差：1.373481e-06 N。
- 最大全局矩平衡残差：1.161729e-21 N·mm。

原始工件哈希见 `raw_result_manifest.json`，逐案例门禁见 `unit_test_results.json`。
