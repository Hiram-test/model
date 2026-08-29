# 张靖皋猫道成果索引

更新时间：2026-08-29  
项目代码：`CATWALK`  
对象：张靖皋长江大桥南航道桥施工猫道

## 1. 当前结论先看这里

当前猫道研究不是一条已经封板的“最终模型”，而是七类彼此有边界的成果：原始资料、附件参考、理论模型、ANSYS、CalculiX、降阶抖振和独立审计。

当前推荐执行顺序为：

`CW-SRC-01` 原始资料 → `CW-REF-01` 附件参考 → `CW-TH-*` 理论判据 → `CW-ANS-01` 冻结历史证据 → `CW-ANS-02` 干净动力输入 → 实际静力门禁 → 摄动模态 → 零载瞬态 → 多振幅自由衰减 → 抖振解锁。

现阶段唯一活动的 ANSYS 输入入口是 [`feat/catwalk-ansys-clean-dynamics`](https://github.com/Hiram-test/model/tree/feat/catwalk-ansys-clean-dynamics) 和 [PR #26](https://github.com/Hiram-test/model/pull/26)。它只表示输入文件已经建立，不表示求解已经通过。

现阶段唯一活动的完整三维 CCX 入口是 [`cursor/agentic-catwalk-fea-d416`](https://github.com/Hiram-test/model/tree/cursor/agentic-catwalk-fea-d416) 和 [PR #23](https://github.com/Hiram-test/model/pull/23)。该线仍处于硬门禁未闭合状态。

## 2. 统一成果编号

| 编号 | 成果 | 位置 | 状态 | 正确用途 |
|---|---|---|---|---|
| `CW-SRC-01` | 张靖皋完整原始资料归档 | Release [`zhangjinggao-full-20260729`](https://github.com/Hiram-test/model/releases/tag/zhangjinggao-full-20260729) | `ARCHIVE` | 恢复图纸、附件、报告、原始工程文件 |
| `CW-REF-01` | 附件 2-3 参考模型资产 | Release [`catwalk-attachment23-v2.0-s10-20260716`](https://github.com/Hiram-test/model/releases/tag/catwalk-attachment23-v2.0-s10-20260716) | `FROZEN_EVIDENCE` | 查阅 S10 历史 DB 和中心线 STEP；不能直接当新的动力基态 |
| `CW-TH-01` | 十三个纯力学理论模型原始归档 | [`feat/catwalk-thirteen-theory-models`](https://github.com/Hiram-test/model/tree/feat/catwalk-thirteen-theory-models), [PR #16](https://github.com/Hiram-test/model/pull/16) | `FROZEN_ARCHIVE` | 保存 PDF、TeX、TXT 和可复现包，不改写原文 |
| `CW-TH-02` | 双 MCT 扭转理论整合与修正 | [`cursor/mct-torsion-theory-fix-d416`](https://github.com/Hiram-test/model/tree/cursor/mct-torsion-theory-fix-d416), [PR #21](https://github.com/Hiram-test/model/pull/21) | `REVIEW_ONLY` | 理论讨论、跨路径汇合和时间线；不能覆盖原归档 |
| `CW-TH-03` | 图纸参数候选 η/ε/kc | [`cursor/eta-eps-kc-candidates-b0b4`](https://github.com/Hiram-test/model/tree/cursor/eta-eps-kc-candidates-b0b4), [PR #17](https://github.com/Hiram-test/model/pull/17) | `REVIEW_ONLY` | 参数候选和敏感性，不允许从目标频率反标后冒充图纸值 |
| `CW-ANS-01` | S10→C20→D10→E10→E20 完整 ANSYS 消融链 | [`f99-chain-closure`](https://github.com/Hiram-test/model/tree/f99-chain-closure) | `FROZEN_EVIDENCE` | 查阅既有全模型频率、连接消融、输入和 QA；不再继续追加新工况 |
| `CW-ANS-02` | ANSYS 干净动力重建输入包 | [`feat/catwalk-ansys-clean-dynamics`](https://github.com/Hiram-test/model/tree/feat/catwalk-ansys-clean-dynamics), [PR #26](https://github.com/Hiram-test/model/pull/26) | `ACTIVE_INPUT_ONLY` | 当前静力、摄动模态、零载瞬态、TA1 自由衰减的唯一新入口 |
| `CW-CCX-01` | 974211b2 平面迁移与找形链 | [`feat/catwalk-ccx-20260826`](https://github.com/Hiram-test/model/tree/feat/catwalk-ccx-20260826), [PR #18](https://github.com/Hiram-test/model/pull/18), [PR #19](https://github.com/Hiram-test/model/pull/19) | `SUPERSEDED_REFERENCE` | 坐标、找形和早期 CCX 方法参考；不是完整双幅三维模型 |
| `CW-CCX-02` | 双 MCT CCX 垂度/频率卡 | [`cursor/double-mct-ccx-deck-bfc3`](https://github.com/Hiram-test/model/tree/cursor/double-mct-ccx-deck-bfc3), [PR #20](https://github.com/Hiram-test/model/pull/20) | `REVIEW_ONLY` | 独立 CCX 机制核查 |
| `CW-CCX-03` | 真实三维 CCX / 极端风工作线 | [`cursor/agentic-catwalk-fea-d416`](https://github.com/Hiram-test/model/tree/cursor/agentic-catwalk-fea-d416), [PR #23](https://github.com/Hiram-test/model/pull/23) | `ACTIVE_BLOCKED` | 当前完整三维 CCX 开发与审计；门禁未闭合前不得写成复现成功 |
| `CW-ROM-01` | 双 MCT—门架索—横通道降阶模态与抖振 | [`feat/double-mct-catwalk-buffeting`](https://github.com/Hiram-test/model/tree/feat/double-mct-catwalk-buffeting) | `BOUNDED_REFERENCE` | 模态机制、频域抖振和敏感性参考；不替代完整三维动力模型 |
| `CW-VAL-01` | 附件表 4-1 差异分析 | [`cursor/table41-fable5-diff-d416`](https://github.com/Hiram-test/model/tree/cursor/table41-fable5-diff-d416), [PR #22](https://github.com/Hiram-test/model/pull/22) | `REVIEW_ONLY` | 固定数据的差异汇总，不新增求解结果 |
| `CW-VAL-02` | 猫道结果审计 | [`cursor/catwalk-results-audit-a369`](https://github.com/Hiram-test/model/tree/cursor/catwalk-results-audit-a369), [PR #25](https://github.com/Hiram-test/model/pull/25) | `REVIEW_ONLY` | 结果来源、输入—输出绑定和结论边界审计 |
| `CW-VAL-03` | 猫道比对协议 | [`cursor/catwalk-comparison-protocol-10d4`](https://github.com/Hiram-test/model/tree/cursor/catwalk-comparison-protocol-10d4), [PR #24](https://github.com/Hiram-test/model/pull/24) | `REVIEW_ONLY` | 统一比较定义、配对与验收口径 |

## 3. ANSYS 当前路线

### `CW-ANS-01`：冻结证据链

`f99-chain-closure` 保存了 S10、C20、D10、E10、E20 和未完成的 E21。它的价值是完整记录已有全模型消融，不是继续充当“最新模型”。

该分支以后只允许：

- 修正文档索引或明显的记录错误；
- 增加不改变原始计算文件的校验清单；
- 为已有文件补充哈希和来源说明。

不得在这个分支继续添加新的静力、模态、瞬态或抖振工况。

### `CW-ANS-02`：当前活动输入

[PR #26](https://github.com/Hiram-test/model/pull/26) 以 `f99-chain-closure` 为审阅基线，只增加 `catwalk-fem/ansys-clean-dynamics/`。输入顺序为：

1. `10_static_equilibrium.inp`：从冻结 APDL 源重新装配并求非线性静力平衡；
2. `20_prestressed_modal.inp`：从干净平衡态提取预应力摄动模态；
3. `30_zero_load_transient.inp`：同一 full-transient 中先平衡，再打开时间积分且不加新增动力荷载；
4. `40_ta1_twist_release.inp`：左右幅反向竖向扰动及释放自振；
5. `50_buffeting_not_armed.inp`：硬锁的抖振占位入口。

任何“ANSYS 当前结果”必须明确写成以下一种状态：

- `INPUT_PREPARED`
- `STATIC_RUNNING`
- `STATIC_GATE_FAILED`
- `STATIC_GATE_PASSED`
- `MODAL_RUNNING`
- `MODAL_GATE_PASSED`
- `ZERO_LOAD_TRANSIENT_PASSED`
- `FREE_DECAY_IDENTIFIED`
- `BUFFETING_ARMED`

不得使用含糊的“算好了”“模型正确”“最终版”。

## 4. CCX 当前路线

`CW-CCX-01` 是从 STEP 和简化平面模型发展出的早期路线，保留坐标和找形经验。其大型 `.frd` 位于 Release [`catwalk-ccx-frd-20260826`](https://github.com/Hiram-test/model/releases/tag/catwalk-ccx-frd-20260826)。它不是完整双幅三维动力模型。

`CW-CCX-03` 是当前真实三维工作线。其任何结果必须同时报告：

- 生成器提交 SHA；
- 最终 `.inp` SHA-256；
- CCX 版本；
- 静力收敛和全局反力闭合；
- 残余刚体模态；
- 网格/粗化敏感性；
- 模态分类规则；
- 是否允许形成结论。

只要状态仍为 `ACTIVE_BLOCKED`，该线只能作为开发和比较记录。

## 5. 理论、降阶与全模型之间的关系

三类模型各自回答不同问题：

- `CW-TH-*`：解释物理机制、可达域和参数可识别性；
- `CW-ROM-01`：验证拓扑、模态族、气动力流程和敏感性；
- `CW-ANS-*` / `CW-CCX-*`：检验完整离散模型、实际连接、质量和动力状态。

它们可以交叉验证，但不能互相替代。理论对上某一频率不等于全模型已正确；全模型收敛也不等于理论机制或附件配对已正确。

## 6. 开放 PR 导航

| PR | 名称 | 本索引状态 | 处理原则 |
|---:|---|---|---|
| [#16](https://github.com/Hiram-test/model/pull/16) | 十三模型理论归档 | `FROZEN_ARCHIVE` | 保留原文件；后续可单独决定是否并入稳定归档分支 |
| [#17](https://github.com/Hiram-test/model/pull/17) | η/ε/kc 参数候选 | `REVIEW_ONLY` | 不合并为权威参数 |
| [#18](https://github.com/Hiram-test/model/pull/18) | CCX 坐标门和初始输入 | `SUPERSEDED_REFERENCE` | 保留坐标与输入历史 |
| [#19](https://github.com/Hiram-test/model/pull/19) | 974211b2 找形与工况 | `SUPERSEDED_REFERENCE` | 保留找形证据，不当完整三维动力模型 |
| [#20](https://github.com/Hiram-test/model/pull/20) | 双 MCT CCX 频率卡 | `REVIEW_ONLY` | 机制核查 |
| [#21](https://github.com/Hiram-test/model/pull/21) | 双 MCT 扭转理论修正 | `REVIEW_ONLY` | 与 `CW-TH-01` 区分原文和后续综合 |
| [#22](https://github.com/Hiram-test/model/pull/22) | 表 4-1 差异分析 | `REVIEW_ONLY` | 只引用锁定数据，不冒充新计算 |
| [#23](https://github.com/Hiram-test/model/pull/23) | 猫道 agentic FEA | `ACTIVE_BLOCKED` | 当前 CCX 三维开发线 |
| [#24](https://github.com/Hiram-test/model/pull/24) | 猫道比对协议 | `REVIEW_ONLY` | 作为比较规则，不当计算结果 |
| [#25](https://github.com/Hiram-test/model/pull/25) | 猫道结果审计 | `REVIEW_ONLY` | 作为证据审查入口 |
| [#26](https://github.com/Hiram-test/model/pull/26) | ANSYS 干净动力输入包 | `ACTIVE_INPUT_ONLY` | 当前 ANSYS 唯一活动输入线 |

## 7. Release 使用顺序

需要恢复原始工程资料时，先进入 `CW-SRC-01`，读取 Release 内的 manifest 和 package-members，再按清单下载分卷。

只需要历史 S10 DB 或 STEP 时，使用 `CW-REF-01`。该 DB 保留历史价值，但不能绕过当前干净动力链的静力重建和瞬态状态验证。

需要 974211b2 CCX 大型结果时，使用 `catwalk-ccx-frd-20260826`，并同时阅读分支和 PR 中的适用边界。

## 8. 禁止事项

- 不再创建名称只有 `final`、`latest`、`complete` 或随机后缀而无项目代码的分支；
- 不把 `main`、Release 日期或文件体积当作有效性证明；
- 不在同一运行目录覆盖 `.db`、`.rst`、`.rstp`、`.frd` 或求解日志；
- 不在理论、ROM、ANSYS 和 CCX 之间用“第 n 阶”直接硬对齐，必须按物理模态身份配对；
- 不在静力、零载瞬态和自由衰减门禁通过前解锁抖振；
- 不删除现有分支，除非先在 [`docs/BRANCH_REGISTER.md`](docs/BRANCH_REGISTER.md) 中给出替代入口和保留证据。
