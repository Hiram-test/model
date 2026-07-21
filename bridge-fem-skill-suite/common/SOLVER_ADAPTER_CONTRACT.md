# 求解器适配器契约

求解器适配器只负责 `FEM-IR ↔ solver deck/result` 转换，不得重新解释工程输入。

## 必需接口

- `capabilities()`：返回求解器版本与 feature matrix；
- `compile(fem_ir, controls)`：生成 deck、mapping 和静态差异报告；
- `validate_deck(deck, fem_ir)`：回读对象、属性、荷载和边界；
- `run(deck, environment)`：执行并返回 run record；
- `inspect_run(run_record)`：分类 fatal、warning、nonconvergence；
- `extract(raw_results, output_requests)`：生成统一结果字段；
- `round_trip_map()`：提供 IR 对象、solver entity 和结果字段双向映射。

## Feature 状态

- `SUPPORTED_EXACT`：语义直接等价；
- `SUPPORTED_APPROVED_EQUIVALENT`：使用已批准等效，并绑定验证证据；
- `SUPPORTED_WITH_LIMITS`：只在声明条件内可用；
- `UNSUPPORTED`：阻断依赖该特性的用途。

## 强制记录

适配器版本、模板版本、求解器可执行文件哈希、单位转换、对象映射、默认值覆盖、deck diff、命令行、环境、日志、重试、原始结果哈希和字段符号。

## 验证要求

每个支持 feature 至少有一个最小样例。梁、壳、索、弹簧、MPC、释放、偏心、初应变、阶段、非线性和接触分别测试。版本升级后运行全部适用黄金样例。
