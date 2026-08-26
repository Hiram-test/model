# 恒总荷载迁移 APDL 语法微验证

状态：`LOAD_MIGRATION_PARAMETER_EXPRESSION_AND_ZERO_REPLACEMENT_SYNTAX_PASSED`。

- MAPDL 2026 R1 正常退出，错误=0、警告=0。
- `F,node,FZ,C10_BETA*(value)` 被求解器正常识别。
- 同一节点在 beta=1 时位移为 `6.25×10⁻⁵ mm`，beta=0 通过 `FCUM,REPL` 显式写零后位移为 `0 mm`。
- 第二步 `KBC=0`、20 个子步；迁移阶段没有使用 `FDELE`。
- 本微验证设置 `NLGEOM=OFF`，所以输出中的 `CNVG=0` 是线性分析下不适用的活动状态字段，不表示求解失败；端点结果和求解器错误/警告才是本次语法门。
- 该两节点模型只验证 APDL 表达式与 replacement 更新语义，不代表全桥静力或生产通过。
