# 分支登记表

盘点时间：2026-08-29  
盘点范围：`Hiram-test/model` 当前全部分支  
说明：本表的状态用于导航和版本管理，不等同于科学有效性或工程签认。

## 1. 处置原则

- `KEEP_ACTIVE`：当前活动入口，不得被旧分支替代。
- `KEEP_FROZEN`：冻结证据或归档，原则上只补索引、哈希和勘误。
- `KEEP_REVIEW`：保留审阅价值，但不能作为当前模型入口。
- `CANDIDATE_RETIRE`：已有明确替代入口；第二阶段确认无未解析引用后可关闭 PR 或删除分支。
- `SEPARATE_PROJECT`：属于其他项目，继续保留，但从猫道导航中隔离。
- `TEMPORARY`：用于本次仓库整理，合并后可删除。

当前分支均未启用 GitHub branch protection。关键冻结分支在后续清理前应先建立保护规则或不可变标签。

## 2. 张靖皋猫道分支

| 分支 | 短 SHA | 状态 | 关联 | 当前用途 | 建议处置 |
|---|---|---|---|---|---|
| `feat/catwalk-ansys-clean-dynamics` | `2f924fb` | `ACTIVE_INPUT_ONLY` | PR #26 | 当前 ANSYS 干净静力、摄动模态、零载瞬态和自由衰减输入 | `KEEP_ACTIVE` |
| `f99-chain-closure` | `2c7e7cd` | `FROZEN_EVIDENCE` | — | S10→C20→D10→E10→E20 完整 ANSYS 历史消融链；也是 PR #26 的审阅基线 | `KEEP_FROZEN` |
| `cursor/agentic-catwalk-fea-d416` | `f9476d1` | `ACTIVE_BLOCKED` | PR #23 | 当前真实三维 CCX 与极端风开发线 | `KEEP_ACTIVE` |
| `feat/catwalk-thirteen-theory-models` | `33662f9` | `FROZEN_ARCHIVE` | PR #16 | 十三个纯力学理论模型 PDF、TeX、TXT 和可复现包 | `KEEP_FROZEN` |
| `feat/double-mct-catwalk-buffeting` | `cfbf39e` | `BOUNDED_REFERENCE` | — | 双 MCT 降阶模态、频域抖振和敏感性包 | `KEEP_FROZEN` |
| `cursor/mct-torsion-theory-fix-d416` | `68686b3` | `REVIEW_ONLY` | PR #21 | Fable 扭转理论修正、讨论和跨路径整合 | `KEEP_REVIEW` |
| `cursor/table41-fable5-diff-d416` | `09fb56d` | `REVIEW_ONLY` | PR #22 | 附件表 4-1 与锁定结果差异分析 | `KEEP_REVIEW` |
| `cursor/catwalk-comparison-protocol-10d4` | `2c6a579` | `REVIEW_ONLY` | PR #24 | 猫道模型比较、配对和验收协议 | `KEEP_REVIEW` |
| `cursor/catwalk-results-audit-a369` | `0b01dbf` | `REVIEW_ONLY` | PR #25 | 猫道结果来源和结论边界审计 | `KEEP_REVIEW` |
| `cursor/eta-eps-kc-candidates-b0b4` | `10eb1d0` | `REVIEW_ONLY` | PR #17 | 图纸参数候选与理论敏感性 | `KEEP_REVIEW` |
| `cursor/double-mct-ccx-deck-bfc3` | `bec5de3` | `REVIEW_ONLY` | PR #20 | 双 MCT CCX 垂度和频率卡 | `KEEP_REVIEW` |
| `cursor/catwalk-inp-coord-gate-bbc1` | `41677f3` | `SUPERSEDED_REFERENCE` | PR #18 | STEP→CCX 坐标门和早期输入链 | `KEEP_REVIEW`，待 `CW-CCX-01` 归档后评估关闭 |
| `cursor/catwalk-main-deck-gate-f23d` | `ac93c8c` | `SUPERSEDED_REFERENCE` | PR #19 | 974211b2 找形、六工况和早期动力卡 | `KEEP_REVIEW`，不作为完整三维模型 |
| `feat/catwalk-ccx-20260826` | `ebd0e3d` | `SUPERSEDED_REFERENCE` | Release `catwalk-ccx-frd-20260826` | 974211b2 平面迁移模型及大型 CCX 文件来源 | `KEEP_FROZEN`，从活动入口移除 |
| `agent/add-catwalk-execution-log` | `f254aa6` | `SUPERSEDED` | — | 第一版执行日志 | `CANDIDATE_RETIRE`，先核对 v2 是否完整覆盖 |
| `agent/add-catwalk-execution-log-v2` | `dddee74` | `FROZEN_EVIDENCE` | — | 第二版执行日志 | `KEEP_FROZEN` |
| `agent/skill-runtime-ansys-audit` | `f5fccc7` | `FROZEN_EVIDENCE` | — | Skill/ANSYS 运行与保真度审计 | `KEEP_FROZEN` |
| `audit/cross-passage-design-source-20260801` | `6eb1e3f` | `ARCHIVE_AUDIT` | — | 横向通道设计来源审计 | `KEEP_FROZEN` |
| `audit/release-inventory-20260803` | `b9a65e3` | `ARCHIVE_AUDIT` | — | Release 和附件清点 | `KEEP_FROZEN` |
| `audit/step-release-drafts-20260801` | `f9741ee` | `ARCHIVE_AUDIT` | — | STEP/Release 草稿审计 | `KEEP_FROZEN`；确认被 release inventory 覆盖后再评估 |
| `agent/archive-zhangjinggao-20260729` | `37dd665` | `ARCHIVE` | PR #10 / Release `zhangjinggao-full-20260729` | 约 77 GB 张靖皋资料归档、清单和恢复脚本 | `KEEP_FROZEN` |

## 3. 扎青吊桥分支

扎青吊桥与张靖皋猫道分开管理，以下分支统一标记为 `SEPARATE_PROJECT`。

| 分支 | 短 SHA | 已知用途 | 建议处置 |
|---|---|---|---|
| `agent/zhaqing-freecad-cad003` | `0f5e77e` | CAD-003 与图纸证据链，关联 PR #9 | 保留为扎青 CAD 主审阅线 |
| `agent/zhaqing-prestress-isolation` | `8d0561c` | 预应力隔离研究，关联 PR #13 | 保留 |
| `agent/zhaqing-prestress-fix` | `f6ec167` | 预应力修正试验 | 保留至 PR 关系核清 |
| `agent/zhaqing-prestress-calibration-run` | `4797018` | 完成态预应力校准运行 | 保留至 PR #15 关闭或归档 |
| `agent/zhaqing-formfind-final` | `c7d8d97` | 找形阶段成果 | 禁止仅凭 `final` 判断权威；补扎青项目索引后再定 |
| `agent/zhaqing-native-solve-only` | `d743ede` | 原生求解专用分支 | 保留至扎青求解谱系清点 |
| `work/zhaqing-rebuild-20260722` | `7ddb39e` | 早期重建工作线 | `CANDIDATE_RETIRE`，先核对是否仍有独有文件 |

## 4. Skill、流程与方法分支

| 分支 | 短 SHA | 状态 | 已知用途 | 建议处置 |
|---|---|---|---|---|
| `agent/add-bridge-fem-lifecycle-hooks` | `7b0130b` | `PUBLISHED_TOOLING` | N00–N18 生命周期 hooks，关联 PR #6 | 保留至稳定集成确认 |
| `agent/installable-skill-suite-cleanup` | `a51f79b` | `PUBLISHED_TOOLING` | Skill Suite 安装包整理 | 保留至与 `main` 的发布包核对完成 |
| `agent/document-box-geometry-failure` | `c5d0be5` | `REVIEW_ONLY` | 盒子代理几何失败复盘，关联 PR #7 | 保留文档证据 |
| `agent/document-cad-skill-lessons` | `77a2737` | `REVIEW_ONLY` | CAD Skill 经验与边界 | 保留至与 PR #8/9 关系核清 |
| `feat/tbeam-vla-benchmark-code-only` | `b0dc66f` | `SEPARATE_PROJECT` | T 梁 VLA 基准代码 | 建立独立 T 梁索引后保留 |
| `代理式预研` | `c9b21a3` | `SEPARATE_PROJECT` | 代理式方法预研 | 保留；新工作改用英文规范名，旧分支不强制改名 |

## 5. 集成与本次整理分支

| 分支 | 短 SHA | 状态 | 用途 | 建议处置 |
|---|---|---|---|---|
| `main` | `110367b` | `INTEGRATION` | 稳定公共工具、历史根目录文件和仓库导航 | 保留；合并索引后不把它称为最新计算模型 |
| `chore/repository-index-20260829` | `110367b`（创建时） | `TEMPORARY` | 本次 README、总索引、猫道索引、分支表和命名规则 | 合并后删除分支 |

## 6. 第二阶段候选动作

以下动作尚未执行：

1. 检查 `agent/add-catwalk-execution-log` 是否被 v2 完整覆盖；若覆盖，关闭关联 PR 并删除旧分支；
2. 给 `f99-chain-closure`、理论归档和完整资料归档创建保护规则或冻结标签；
3. 为 PR #18、#19 补充“已由 `CW-CCX-03` 取代活动入口”的顶部说明，再决定关闭而非直接删除；
4. 单独建立扎青项目索引，核清 PR #8、#9、#13、#14、#15 与分支的准确对应；
5. 把 `main` 根目录散落的猫道文件迁入项目目录，并提交旧路径—新路径—SHA 映射；
6. 整理完成后再批量关闭 PR 和删除分支。

任何分支删除前，必须满足：有替代入口、独有文件已核对、开放 PR/Issue 无未处理引用、必要提交已打标签或进入 Release。
