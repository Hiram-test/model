# A10 准备与轴审计字段说明

本目录内 JSON 和 CSV 保持严格机器语法，因此不在文件内部添加注释；本说明承担逐项解释。

## h175_axis_audit.csv

每行对应一个 MAT=61、SECNUM=61、TYPE=70 的 BEAM188 元素，共 2698 行。element_id 与 line_number 字段定位 EN/N 命令；i/j/k_node 是节点号；i、j、old_k、new_k 和 old/new_ki 字段单位均为 mm；ex/ey/ez 是单位向量；三个 dot 字段和 right_handed_triple_product 审计正交右手系；old_n_command/new_n_command 是唯一允许变化的 APDL 行。

## h175_axis_summary.json

formula 固定四步局部轴公式；target 记录属性编号与 2698 数量闭合；exclusive_k_nodes 表示 K 节点未被任何 EN 当作 I/J；representative 字段验证 K-I 约为 -global X；max_* 字段给出正交、右手和重构误差；maximum_output_line_length 必须不超过 640。

## input_hash_audit.csv

每行是一项依赖。role=invariant 的 10 项必须在 B00 snapshot、B00 solver、A10 snapshot、A10 solver 四处同哈希；role=controlled_axis_change 的 include 要求两个 B00 副本同哈希、两个 A10 副本同哈希且新旧不同。expected_b00_sha256 来自 frozen B00 manifest。

## model_single_difference_audit.json

physical_change_family_count 必须为 1；唯一家族是 2698 个 H175 K 方向节点。canonicalized_modified_sha256 等于 frozen_source_sha256 表示把这些目标行还原后全文逐字闭合。forbidden_changes 全为 false，说明 Iyy/Izz、E、密度、质量、索力、CERIG/CP、网格和剪切参数未变。

## main_control_flow_audit.json 与 b00_old_to_current_control_flow.patch

PATCH 仅记录 frozen B00 旧主输入到当前 B00 单作业模板的非物理控制修正；JSON 记录修正版模板哈希、A10 机械身份化、80 阶无频带上限、真实 LS2、严格结果数闭合、ALL,NONE 后显式恢复 NSOL/VENG 及 GATE_BOTTOM_E 每阶 SENE 注入。此差异不计入模型物理单差异。

## manifest.json、A10_status.json 与 preflight.json

manifest 固定父 B00、jobname、依赖、求解契约、能量输出和未来 argv；A10_status 可报告 PREPARED_WAITING_RESOURCES、PREPARED_NOT_STARTED 或 PREPARED_NOT_STARTED_USER_OVERRIDE，mapdl_started/process_started/execution_attempted 永远为 false；preflight 分别记录实测资源和 USER_OVERRIDE。任何 READY/RUNNING 状态均不由本脚本产生。

## source_hashes.sha256 与 artifact_hashes.sha256

source_hashes 绑定 frozen B00 输入、当前 B00 模板源码、A10 编排器和生成输入；artifact_hashes 枚举除自身外的 run 内全部文件。每行格式为 SHA-256、两个空格、标签。

## 未来 a10_gate_bottom_modal_sene.csv

该文件仅在未来显式启动 MAPDL 后由主 APDL 生成，无标题四列依次为 mode_index、total_sene_n_mm、gate_bottom_sene_n_mm、gate_bottom_sene_ratio；准备阶段不会创建空结果文件。
