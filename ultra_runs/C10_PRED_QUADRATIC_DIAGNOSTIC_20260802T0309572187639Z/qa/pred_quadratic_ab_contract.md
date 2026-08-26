# PRED,QUADRATIC 单变量重启 A/B 合同

- 唯一运行：`C10_PRED_QUADRATIC_DIAGNOSTIC_20260802T0309572187639Z`；唯一 job：`cw_C10pq_0802030957223`。
- 来源仅为冻结运行 `C10_LOAD_MIGRATION_DIAGNOSTIC_20260801T234415577134Z` 的 R001、R002、RDB、LDHI、RST；没有使用前一 NRRE 诊断运行中的任何可写重启文件。
- 重启点：载荷步 2、已接受子步 2；来源累计平衡迭代为 93。
- 唯一待检算法变量：`PRED,OFF` 改为 `PRED,QUADRATIC`。
- 不变项：同一源状态、同一载荷与约束、`NROPT,FULL`、`LNSRCH,ON`、同一载荷步 2 子步 3。
- 诊断控制：`NLDIAG,NRRE,ON,50`、`NEQIT,8`、`NCNV,1,,101`；最多约八次新增迭代。
- 终止规则：子步接受则正常退出；未接受则由 MAPDL 自身迭代限额退出。禁止 `terminate`、`kill`、`send_signal` 或 ABT 外部终止。
- 结果用途：仅比较二次预测器相对 `PRED,OFF` 基线十二次未收敛的改善，不构成静力、模态、设计或生产发布许可。
