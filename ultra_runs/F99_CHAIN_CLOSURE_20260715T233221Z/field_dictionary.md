# F99 终态包字段说明

## CSV 通用约定

- `NOT_RUN` 表示没有启动对应全桥 MAPDL，绝不等同于数值为零或门禁通过。
- `NOT_CREATED` 表示没有合法父线，因而没有创建该变体目录或输入。
- `REJECTED` 是任务书五态中的执行链拒绝结论；`reason` 说明拒绝范围。对未执行变体，该词不表示物理方案已被频率结果否定。
- `PHYSICALLY_CORRECT_NOT_DOMINANT` 表示源证支持物理定义，但当前证据不足以宣称其对 14 个报告目标的频移因果已经封板。

## `04_run_matrix_actual.csv`

- `sequence`：任务书最小全桥矩阵中的顺序号。
- `authoritative_run`：唯一引用的权威目录；`NOT_CREATED` 时不存在可引用运行。
- `mapdl_started`：该行对应的独立变体是否启动过 MAPDL。A30 通过 A10 输入等价复用，因此本字段为 `false`，而 `physical_execution_completed` 为 `true`。
- `from_scratch_required`：该物理变体若执行是否必须重新做非线性静力。
- `physical_execution_completed`：是否已有合法全桥结果，或零物理差异使重复求解不产生新信息。
- `taskbook_decision`：采用任务书允许的五态之一；未执行链统一以 `REJECTED` 表示当前不得进入下一步。

## `05_static_gates.csv`

- 能量比均为无量纲，反力误差为相对误差，总质量误差单位为 tonne。
- `CONTROL_FLOW_OFF_NUMERIC_HISTORY_NOT_SAVED` 表示两次求解均由 OUT 证明 `STABILIZE,OFF` 在 `SOLVE` 前生效，但 A10 的逐子步 STEN 数值曲线未保存；该限制不得改写成数值峰值已知。
- A30 数值来自与其字节等价的 A10 全桥结果复用；A20 为零物理差异，不产生独立静力行。

## `12_parameter_decisions.csv`

- `SOURCE` 为图纸或报告直接来源；`DERIVED_FROM_GEOMETRY` 为由图纸/生成几何推导；`IDENTIFIED_WITH_BOUNDS` 为经单元级数值对照且保留适用边界。
- `PREPARED_NOT_EXECUTED` 表示参数已进入独立输入快照但未通过全桥静力和模态门禁，不能进入生产模型。
- `HARD_SOURCE_EVIDENCE_BLOCK` 表示缺失报告原始数值向量，无法通过进一步解析现有截图恢复双精度节点向量。

## Markdown 与 JSON

JSON、CSV 和 SHA-256 账本格式不支持注释；本文件承担字段、单位和状态口径的邻接说明。最终 `status.json` 只汇总事实，不覆盖各权威子包的原始状态。
