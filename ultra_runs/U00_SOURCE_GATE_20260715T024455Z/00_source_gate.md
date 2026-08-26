# U00 可执行源门禁

- 生成时间：`2026-07-15T02:55:26.983819+00:00`
- 状态：`PASS_A`
- 必需源项：38 项；缺失：0 项。
- MAPDL：`D:\ANSYS2026\ANSYS Inc\v261\ansys\bin\winx64\ANSYS261.exe`；存在：`True`；SHA-256：`6c6327f6b906db8e6dd498bd38c97685d7e3e4acf52fccbf243b2dff7ed7af1b`。
- 当前可用物理内存：1.55 GiB；全桥最低门槛：8.00 GiB；当前允许启动全桥：`False`。
- B00 LEGACY冻结拓扑：`D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\builder\generated\apply_finite_gates_and_passages_v2.inp`。
- B00 LEGACY冻结质量：`D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\apply_dynamic_mass21_spatialized_v2.inp`。
- C10 MPC诊断封板：`D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs\U00_SOURCE_GATE_20260715T024455Z\regenerated_source_chain\builder_generated`。
- C10 MPC诊断质量：`D:\张靖皋大桥\03_猫道动力分析\附件2-3全模态精确对齐_V2.0\ultra_runs\U00_SOURCE_GATE_20260715T024455Z\regenerated_source_chain\mass_generated`。

## 判定

完整 runner、九个权威基础 include、有限拓扑 builder 及产物、质量生成器及产物、几何/站位/横通道模板和 MAPDL 可执行文件均存在时判 `PASS_A`。固定主输入不作为静态源文件保存，而由 runner 为独立 Run 生成；其可重建性由上述源链共同控制。
源链存在两条不可互换的 lineage：根 `builder/generated` 与根质量 include 是 B00 所需的冻结旧 CERIG 物理基线；隔离重生的 MPC184=8202 拓扑与同代质量 include 是后续 C10 诊断候选。隔离重生产物与历史 `0221` 快照逐字节一致。两条线都通过 U00 哈希封存，但任何拓扑和质量 pair 禁止交叉使用。

## 当前执行边界

U00 只完成只读源审计，不启动 MAPDL。`PASS_A` 后下一步只能进入 U01 小算例；只有 U01 全部通过且可用物理内存恢复到至少 8 GiB，才能启动 B00 全桥重算。

## 机器文件说明

- `source_inventory.csv` / `01_source_inventory.csv`：逐项记录类别、用途、绝对路径、硬门禁标志、存在性、字节数、UTC 修改时间和 SHA-256。
- `input_dependency_graph.json`：记录显式 `/INPUT` 依赖、Python 动态生成关系和未解析 include。
- `mapdl_environment.json`：记录求解器身份、Windows/Python/CPU、DMP/Intel MPI、四进程和内存门禁。
- `U00_status.json`：记录唯一合法状态、缺失项、主输入可重建性及下一步。
- `source_hashes.sha256`：绑定所有已找到关键源文件的原始字节内容。
