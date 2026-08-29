# Agentic Catwalk · CalculiX 零导入预应力试建

项目：`CW-ZJG-AGENTIC-CATWALK`  
Run：`CW-CCX-ZF-SMK-20260829-01`  
状态：`BLOCKED_AT_G8B / PASS_STATIC_SMOKE_ONLY`

本目录按既有 N00–N18 Bridge FEM Skill 组织一条新的猫道 CalculiX 试建路线。它不恢复 S10 DB，不读取 MCT `*INIFORCE`，不使用目标频率反标，也不把既有 CCX 结果当成新的初始状态。

本次只完成：

- 主跨双幅等效索线的缩减烟测几何；
- 从零导入应力起步的逆向无应力几何找形方案；
- 位移控制成形、恒载释放和无增量保持的 CCX 草案；
- 19 个 Skill 的冻结任务包、门禁台账和工件谱系；
- 输入静态检查和外层更新方向烟测；
- 候选动力扩展 Skill；
- 既有和本次错误经验台账。

本次没有 CCX 可执行文件，因此没有进行有限元求解。`PASS_STATIC_SMOKE_ONLY` 只表示生成器和静态检查通过，不能解释为静力收敛、找形成功或动力可用。

## 一、核心路线

目标加载态来自图纸/复核报告控制点；未来可用 STEP 或 MCT 节点坐标加密，但它们只提供几何。

\[
X^{0,(k)}
\overset{\text{零初始应力}}{\longrightarrow}
\text{位移控制成形}
\longrightarrow
\text{撤除临时控制并施加恒载}
\longrightarrow
X^{L,(k)}
\]

外层更新：

\[
X^{0,(k+1)}
=
X^{0,(k)}
-\alpha\left(X^{L,(k)}-X^\star\right)
\]

其中：

- \(X^0\)：本轮无应力参考几何；
- \(X^L\)：本轮恒载平衡后的加载几何；
- \(X^\star\)：图纸/STEP/MCT 的目标加载几何；
- \(\alpha=0.35\)：本次烟测冻结的松弛系数，只是数值种子。

每轮重建参考几何并把初始应力重新置零。MCT 索力、S10 初应力和附件频率均不进入更新。

## 二、为什么不直接把目标曲线以零应力送进静力求解

离散索链在零轴力下可能具有横向机构，第一步 Newton 切线刚度即可奇异。这个问题不能通过放宽残差、增加全网约束或导入 MCT 索力掩盖。

本次采用的首选路径是：

1. 从一条比目标加载态略浅的无应力参考曲线开始；
2. 临时控制内部节点到目标几何，形成可追溯的成形路径；
3. 完全撤除内部临时控制；
4. 仅保留物理端部约束并施加恒载；
5. 读取加载后坐标、索力、反力和残差；
6. 外层修正无应力参考几何；
7. 收敛后增加无新增荷载保持步。

临时位移不是物理支承，也不能保留到接受状态。

## 三、正式 19 节点状态

| 节点 | 当前状态 | 说明 |
|---|---|---|
| N00–N09 | `PASS / PASS_WITH_BOUNDS` | 仅对本次缩减烟测范围成立 |
| N10 | `BLOCKED` | 没有 CCX 平衡、索力、反力和保持步结果 |
| N11–N18 | `NOT_ACTIVATED` | 根据 orchestrator 规则，不允许消费被阻断的初始状态 |
| 动力扩展 | `NOT_ARMED` | 未通过静力初始状态、质量惯量和零荷载瞬态门 |

虽然目录中提供了 N11–N14 以后可能使用的草案和动态模板，但它们是 `DEVELOPMENT_ONLY`，不在正式 artifact registry 中。

## 四、目录

- `config/trial_config.json`：本次唯一配置；
- `ir/`：N01–N12 的已登记或草案工件；
- `workflow/`：run plan、19 个任务包、门禁、问题和谱系；
- `solver/drafts/`：未授权执行的 CCX 草案；
- `scripts/build_trial.py`：确定性输入生成器；
- `scripts/zeroform_controller.py`：外层无应力几何更新器；
- `scripts/smoke_check.py`：不调用求解器的烟测；
- `tests/`：烟测输出；
- `FAILURE_LEDGER.md`：禁止重复犯的错误；
- `RUNBOOK.md`：下一步外部执行顺序。

候选动力 Skill 位于：

`bridge-fem-skill-suite/extensions/19-catwalk-nonlinear-dynamics/`

## 五、当前烟测结果

共 16 项检查全部通过：

- 34 个节点、49 个 T3D2 单元；
- 无悬空节点引用和零长度单元；
- 目标垂度 227.300 m 闭合；
- 两幅目标线形对称；
- 输入中不存在 MCT/S10 初始应力或目标频率；
- 解析力只作为独立量级审计，未写入 deck；
- 19 个任务包齐全；
- 正式工作流确实停在 G8B；
- 三个动力模板均为 `NOT_ARMED`；
- 用户可见 Python 每个非空代码行均带注释；
- 当前环境未发现 CCX 可执行文件，该事实已如实登记。

## 六、当前结论

\[
\boxed{
\text{已建立 agentic zero-formfinding 输入与门禁原型，}
\quad
\text{尚未建立可接受的猫道静力初始状态。}
}
\]

下一次有效动作不是跑完整三维或抖振，而是在固定 CCX 版本上执行这个缩减单元链，获得第一次真实的加载坐标、索力、反力和保持步数据。
