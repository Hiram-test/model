# S10_SOURCE_GATE 缺口清单

## 当前阻断项

1. `RESOURCE-MEMORY`：可用物理内存 4,451,053,568 byte，小于 8 GiB；还需释放至少 4,138,881,024 byte。此项阻断 MAPDL 启动。
2. `RESOURCE-DISK`：D 盘可用 30,100,930,560 byte，小于 32 GiB；还需释放至少 4,258,807,808 byte。磁盘门禁不可由内存覆盖替代，此项独立阻断 MAPDL 启动。

## 已修复的源门禁缺口

1. `S10-PARENT-STALE`：准备脚本原先固定旧 A30；已切换到最终 `A30_ALL_AXES_20260715T230922215766Z` 和 manifest SHA-256 `217779...0b71`。
2. `S10-U01-UNREACHED`：U01 四份原始 CSV、十二对响应与模板复算函数原先未接入主路径；现已 fail-closed 调用。
3. `S10-U02-UNREACHED`：LS1 全历程 U02 微测函数原先未接入主路径；现已 fail-closed 调用。
4. `S10-FIXED-HASH-UNUSED`：U01 manifest 和四份 CSV 的固定哈希原先仅声明未比较；现已逐项闭合，并额外复算 U01/A30/U02 完整产物账本。

以上四项均已关闭，当前没有剩余 S10 源侧阻断项，源侧状态为 `PASS_TO_PREPARE`。

## 运行后必须继续判定的项目

1. 新 S10 全桥必须真实满足 MAPDL ERROR=0、negative/zero pivot=0、LS1/LS2 收敛和第 14 节全部数值阈值；只读源审计不能提前声明这些结果。
2. A30 的全历程 STEN/SENE 数值曲线未保存，但 S10 当前控制模板会保存并判定全历程；必须以未来 S10 自身结果封板。
3. A30 的 14 个目标物理振型 mapping/MAC 尚未闭合；不阻断 S10 因果变体启动，但阻断最终报告物理映射封板。
4. native 自动 J 与冻结生产 J 最大相差 7.087934%；native 只能作为剪切柔度参考，禁止直接用 native J 覆盖 ASEC 生产值。

## 下游隔离项

1. 当前 U00/C10 候选 include 的 SEC61 Iyy/Izz 相对 A30 发生对调，违反 S10 前六字段不变边界。当前 C10 候选应保持 `REJECTED_TO_LAUNCH`，后续须从正式 S10 封板输入生成纯连接差分；本项不反向阻断 S10。
