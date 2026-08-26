# C10 门架—索接口局部审计设计

## 已闭合的工程量

- 门架：142 座；每座 22 个 `UXYZ` 索接口、34 个物理节点、30 个 BEAM188 单元、34 个空间 MASS21 节点。
- `UXYZ` 接口：3124 个；其中每座含 16 个底索接口和 6 个门架索接口。
- 接口邻接 LINK180：每个 slave 节点恰有两段，共 6248 个唯一单元；不同接口不复用同一相邻索段。
- 接口邻接索节点：离线拓扑闭合得到 9372 个唯一节点，即 3124 个接口节点及其左右相邻节点；POST1 只需导出 3124 个 slave 节点。
- 全模型 LINK180：73692 个；正拉门禁覆盖全量，6248 个接口相邻单元只作局部拓扑与正拉复核，不用于替代门架接口合力。
- 门架质量：质量表中 `system=gate` 的 4828 条记录与 4828 个门架物理节点一一对应，总质量 `323.191107485208 tonne`。有限门架材料 `MP,DENS,61..66=0`，因此门架自重仅由这些空间 MASS21 表达，不应再次按梁体积计重。
- 接口污染证据：3124 个 slave 中有 1152 个还承载 `system=original` 的 MASS21，合计 `75.3191923312262 tonne`；这进一步证明不能把 slave 相邻两段索力直接解释为纯门架边界力。

## 最小 POST1 导出

成功静力最终化后，只读恢复 `<jobname>_eq.db`，绑定 `<jobname>.rst` 并执行 `SET,LAST`。导出五张无标题纯数值表和一张结果身份摘要：

1. `c10_ia_link180_force.csv`：73692 行，`element_id, axial_force_n`；`ETABLE,IA_AXIAL,SMISC,1`。
2. `c10_ia_gate_element_sene.csv`：4260 行，`element_id, sene_n_mm`；`ETABLE,IA_SENE,SENE`。
3. `c10_ia_interface_gate_fsum.csv`：3124 行，`master_node,fx,fy,fz,mx,my,mz`；仅选择 4260 个门架 BEAM188，并对每个唯一 master 执行单节点 `FSUM`。
4. `c10_ia_gate_node_response.csv`：4828 行，`node_id,x,y,z,ux,uy,uz,rx,ry,rz`。
5. `c10_ia_rope_node_response.csv`：3124 行，`slave_node,x,y,z,ux,uy,uz`。
6. `c10_ia_result_identity.txt`：实际 `LSTP/SBST/TIME` 及 LINK180、门架梁、接口、门架节点、slave 节点的 MAPDL 实测数量。

输入只允许 `/CLEAR,NOSTART`、`RESUME`、`/POST1`、`FILE`、`SET`、`FORCE`、选择、`ETABLE`、`SPOINT`、`FSUM`、`*GET`、`*VWRITE`、`FINISH` 和 `/EXIT,NOSAVE` 等只读后处理命令；禁止 `/SOLU`、`SOLVE`、`ANTYPE`、`SAVE`、`RESWRITE`、`RSTCREATE`、删除和改名命令。来源 DB/RST 在准备时冻结 SHA-256，Python 对账前再次复算，证明结果复用没有改写来源运行。

## 局部自由体重建

slave 节点同时连接相邻索段、底横梁/其他结构和非门架质量，因此相邻两段 LINK180 的张力矢量和不是纯门架接口力。主口径改为门架侧隔离：只选择 4260 个门架梁，在每个唯一 master 仅选一个节点并以该 master 为 `SPOINT` 执行 `FSUM`。令门架梁元素节点六分量为 `(Q_beam,M_beam)`，该 master 上属于门架的 MASS21 重力为 `P_mass=(0,0,-m×9806)`，则按 ANSYS 元素节点载荷符号关系重建索系经 TYPE72 施加给门架的等效六分量：

- `F_interface = -Q_beam - P_mass`
- `M_interface = -M_beam`

接口等效六分量作用于 master。以变形后刚臂 `r=x_slave_current-x_master_current` 另行检查 `M_interface≈r×F_interface`；相对偏差不超过 `1E-6`。相邻两段 LINK180 只读取 `SMISC,1` 验证两段均严格受拉。

对每座门架，将 22 个 master 接口六分量与 34 个 MASS21 重力 `W_i=(0,0,-m_i×9806)` 相加。以当前门架质量中心为参考点，同时核对总力和总力矩：

- `ΣF = ΣF_interface + ΣW_i`
- `ΣM = Σ[(r_master-r_ref)×F_interface+M_interface] + Σ[(r_mass-r_ref)×W_i]`

TYPE72 是 direct-elimination rigid beam，没有可独立读取的拉格朗日乘子反力；不得伪造 MPC184 元素力。接口六分量由 gate-only FSUM、master 门架质量修正、`M≈r×F` 与整座自由体残差四者交叉验证符号和遗漏。

## 预先冻结的硬门禁

- 142 座、3124 个接口、6248 个接口邻接 LINK180、9372 个接口邻接索节点、4828 个门架节点、4260 个门架单元和 73692 个全模型 LINK180 全部唯一且数量精确。
- 全模型 73692 个 LINK180 轴力均严格大于 `0 N`；接口相邻 6248 个自然包含在此门禁内。
- 每个 UXYZ 刚臂的变形前后长度误差不超过 `max(1E-6 mm, 1E-9×L0)`。基于节点转动向量的 Rodrigues 方向兼容量只作 REVIEW，不作为硬门禁。
- 每个 UXYZ 的 `||M_interface-r×F_interface||` 除以 `max(||M||,||r×F||,||F||×max(L,1 mm),1 N·mm)` 不超过 `1E-6`。
- 每座门架 `||ΣF||/W ≤ 1E-3`，且 `||ΣF||/Σ||F_interface|| ≤ 1E-6`。
- 每座门架 `||ΣM||/(W×Lchar) ≤ 1E-3`，且 `||ΣM||/Σ||r×F|| ≤ 1E-6`。
- 4260 个门架梁的 SENE 不得低于 `-1E-8 N·mm`，每座门架 SENE 总和必须为正。

## 转角和能量热点

- 节点转角：按 `sqrt(RX²+RY²+RZ²)` 排名。
- 梁转角梯度代理：按两端转角向量差除以初始单元长度排名，单位 `rad/mm`。
- 梁能量密度代理：按 `SENE/volume` 排名，单位 `N/mm²`。
- 同时超过全局 99% 分位和同构件正值中位数 5 倍时标为 `REVIEW`。热点不单独判整体模型失败，也不替代构件、焊缝或节点板设计验算。

## 当前结果无法恢复的量

- direct-elimination TYPE72 的独立约束乘子、节点对作用反力或刚臂本体内力；只能由 gate-only 元素节点合力和自由体平衡间接隔离。
- 未写入 RST 的逐子步接口力、门架转角、梁内力和局部自由体历程；现有 `OUTRES` 只能支持已保存端点，若需要全历程必须新跑并预先请求相应 `NSOL/ESOL`。
- 梁抽象之外的焊缝、节点板、螺栓、局部接触、局部屈曲和应力集中。
- 基于节点 `RX/RY/RZ` 的有限转动参数化独立证明；本方案仅把 Rodrigues 误差作为诊断量，硬门禁使用不依赖参数化的刚臂长度保持。

## 执行依赖与首次烟雾测试

- 来源必须已经写出成功终态 `C10_static_status.json`、原生 gate 通过标记、`<jobname>_eq.db` 和 `<jobname>.rst`，且求解目录不得存在 lock；当前仍在运行或失败的 run 只能执行 `inventory`。
- RST 必须包含最终端点的元素节点载荷、位移、转角、LINK180 `SMISC,1` 与 BEAM188 `SENE`。当前主分析的 `OUTRES,ALL,LAST` 设计上满足端点读取，但不能补回未保存的逐子步历程。
- 首次正式使用前，应在批准的同版本 MAPDL 中对一个独立审计包做 POST1 烟雾测试，确认 `FSUM` 后的 `*GET,FSUM,0,ITEM,FX..MZ`、`/NOPR` 下的 `*VWRITE` 和 NLGEOM 单节点 `SPOINT` 口径可用；随后必须由 `M≈r×F` 与 142 座自由体门禁共同确认力和力矩符号。
- 本口径依赖门架 BEAM188 零密度、门架自重仅由快照中的 4828 条 MASS21 表达，以及门架梁没有另施未入账的节点力、面力或温度等效外载。

## 工具入口

- 只读盘点：`python -B ultra_c10_interface_audit.py inventory --source-run <run>`
- 成功静力后准备新包：`python -B ultra_c10_interface_audit.py prepare --source-run <run>`
- 独立 POST1 完成后对账：`python -B ultra_c10_interface_audit.py reconcile --audit-dir <audit-run>`

脚本不会启动 ANSYS；`prepare` 只创建新的 `C10_INTERFACE_AUDIT_<UTC微秒>` 兄弟目录，拒绝覆盖或写入来源 run。
