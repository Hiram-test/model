# C10 全直接消元微算例验收

状态：`MICRO_VALIDATION_PASSED_FULL_BRIDGE_NOT_RUN`。

- prepare：`C10_MPC_ONLY_20260801T174455429550Z`
- execution：`C10_MICRO_VALIDATION_20260801T174734453810Z`
- 真实运行：15/15；通过：15；失败：0。
- TYPE72 与 TYPE73 均为 direct elimination；罚刚度参数为 `null`。
- 本工件只关闭单连接运动学与六向传力门禁；全桥静力、初始状态路径、装配秩和模态仍为 `NOT_RUN`。

## 数值控制值

- 最大 UXYZ/有限转动接口滑移：0.000000e+00 mm。
- 最大 Rodrigues 位移误差：4.547474e-13 mm。
- 最大全局力平衡残差：2.234645e-24 N。
- 最大全局矩平衡残差：1.161729e-21 N·mm。

原始工件哈希见 `raw_result_manifest.json`，逐案例门禁见 `unit_test_results.json`。
