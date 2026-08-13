# Bridge FEM N00–N18 Hook 执行防线

## 1. 目的

这组仓库级 Hook 处理的范围覆盖整个 N00–N18 生命周期，不只检查 Skill 是否被调用。它重点阻断以下失真：

- 节点没有生成全部契约工件，却宣称当前节点完成；
- Gate 的强制条件未执行或未实现，却填写 `PASS` 或 `PASS_WITH_BOUNDS`；
- 专业节点自行写 Gate 状态；
- N04–N13 未取得正式严格通行，N14 已开始生成 deck 或调用求解器；
- 求解器 deck 补写 FEM-IR 中不存在的物理对象；
- N16、N18 绕过 `verified_result_set` 直接读取原始求解结果；
- N17 在冻结独立复核方法前读取详细原始结果；
- 发布包在 Gate、签认、哈希或可复现性尚未闭合时生成；
- 会话压缩或子代理切换后遗失当前节点、任务包和 Gate 义务。

Hook 只负责生命周期、权限、证据完整性和状态转换。每个工程判据仍需由确定性节点校验器执行，Hook 不会用文件存在或 schema 合法替代工程校验。

## 2. 哪些节点需要 Hook

### 2.1 所有节点：N00–N18

全部节点共享以下 Hook：

- `SessionStart` / `PostCompact`：重新注入 active run、当前节点、上游 Gate 和规定工件；
- `PreToolUse`：阻止越权写 Gate、修改冻结契约、跳过当前节点或进入受限下游；
- `PostToolUse`：保存工具调用摘要和结果哈希，复核冻结契约是否被修改；
- `SubagentStart` / `SubagentStop`：把同一任务包绑定给子代理，并阻止无 Gate receipt 的完成声明；
- `Stop`：当答复出现“节点完成”“Gate PASS”“求解完成”“发布完成”等表述时，检查对应 receipt、逐项条件和工件哈希。

### 2.2 N00：运行初始化与节点转换

N00 必须通过确定性控制命令建立 `current.json`、冻结 Skill/workflow/schema/hook policy 哈希，并使用 `enter Nxx` 进入专业节点。手工写 `current.json`、修改 run 状态或绕过上游 Gate 会被阻止。

### 2.3 N01–N03：基础 Gate receipt

N01–N03 仍需为每条 G0–G2 条件生成机器 receipt。Hook 在节点转换时检查 receipt 的条件数量、执行数量、未实现数量、阻断项、validator 身份、审批和工件哈希。具体来源完整性、OCR 覆盖率、正式规则可用性由各节点确定性 validator 判断。

### 2.4 N04–N13：正式求解前的强制闭环

这十个节点是本次复盘暴露出的主要缺口。Hook 要求：

- G3：8 项全部登记，包含坐标配准、冲突、accepted value 和真实回投；
- G4：8 项全部登记，包含 Part 唯一映射、装配图、传力路径和 orphan audit；
- G5：10 项全部登记，包含唯一处置、representation contract、质量/荷载防重复和批准；
- G6：9 项全部登记，包含拓扑、偏心、节点合并、传力路径和回投；
- G7：9 项全部登记，包含独立属性复算、质量对账和唯一 ledger；
- G8A：9 项全部登记，包含逐自由度边界、约束审计和接口测试；
- G8B：9 项全部登记；确实不适用时只能使用有条件证据的 `NOT_APPLICABLE`；
- G9：10 项全部登记，包含荷载总量、组合规则、施工阶段和重复计入审计；
- G10：10 项全部登记，包含单元物理、网格质量、预先冻结的收敛计划和数值控制；
- G11：10 项全部登记，包含物理预检查、刚体模态、单位测试和上游对账。

`FORMAL` run 进入 N14 时，G3–G11 只接受严格 `PASS`；G8B 经正式条件证明可以 `NOT_APPLICABLE`。任何 `NOT_IMPLEMENTED`、CRITICAL conflict、CRITICAL orphan、高敏感未批准假定或 blocking issue 都会阻断下游。未实现条件可以在完整 receipt 中如实形成 `BLOCKED`，不得包装为有限放行。

### 2.5 N14：solver barrier

命令或工具参数匹配 ANSYS/MAPDL、Abaqus、MIDAS、SAP2000、OpenSees、SOFiSTiK、CalculiX 或 solver deck 写入时，Hook 执行 N14 barrier：

1. 当前节点必须为 N14；
2. G0–G11 的 Gate receipt 必须存在并通过结构及来源检查；
3. 正式 run 的 G3–G11 必须严格 `PASS`；
4. 受保护契约哈希必须与 run 启动时一致；
5. Gate receipt 不得由专业节点直接写入。

### 2.6 N15：解验证入口

N15 的完成声明必须有 G13 receipt，覆盖残差、全局力与力矩、关键自由体、网格收敛、步长/算法敏感性和全部 solver warning。求解器返回码为 0 或子步收敛不能单独触发通过。

### 2.7 N16：只消费经验证结果

N16 直接访问 `.rst`、`.odb`、`.op2` 等原始结果会被阻止。规范复核必须从 `verified_result_set` 和正式 rule pack 进入，缺规则、缺结果资格或缺模型外强制检查时保持阻断。

### 2.8 N17：先冻结独立复核计划

N17 读取详细原始结果前，需要先生成并冻结：

```text
.bridge-fem/runs/<runId>/artifacts/N17/independent_check_plan.json
```

冻结命令将其 SHA-256 写入 current state。后续修改计划会使访问条件失效，避免查看主模型结果后再选择有利方法和容差。

### 2.9 N18：release barrier

release manifest、工程报告数据层、签认记录和发布验证报告只能在 N18 生成。正式发布要求 G0–G15 receipt 完整、逐项校验通过、审批角色齐全、工件哈希一致，并通过确定性 release builder。

## 3. 文件

```text
.codex/hooks.json
.codex/hooks/bridge_fem_hooks.py
.codex/hooks/bridge_fem_run.py
.codex/hooks/bridge_fem_base.py
.codex/hooks/bridge_fem_receipts.py
.codex/hooks/bridge_fem_policy.py
.codex/hooks/node_hook_policy.json
.codex/hooks/gate_receipt.schema.json
.codex/hooks/tests/test_bridge_fem_hooks.py
```

运行时状态默认写入 `.bridge-fem/`，该目录不进入 Git。

## 4. 启用

仓库级 Hook 只有在项目 `.codex/` 配置被信任后才会运行。首次拉取或 Hook 文件发生变化后：

1. 在 Codex CLI 中进入本仓库；
2. 运行 `/hooks`；
3. 查看 `.codex/hooks.json` 和命令内容；
4. 信任当前哈希；
5. 重新开始或恢复会话，确认 `SessionStart` 显示 Hook 已加载。

## 5. 启动与进入节点

正式 run：

```bash
python .codex/hooks/bridge_fem_run.py init \
  --project-id PROJECT-001 \
  --run-id RUN-001 \
  --mode FORMAL
```

进入节点：

```bash
python .codex/hooks/bridge_fem_run.py enter N01
python .codex/hooks/bridge_fem_run.py enter N02
```

`enter` 会检查该节点规定的上游 Gate receipt，并生成冻结任务包：

```text
.bridge-fem/runs/<runId>/task-packets/<nodeId>.json
```

查看状态：

```bash
python .codex/hooks/bridge_fem_run.py status
```

验证一份 receipt：

```bash
python .codex/hooks/bridge_fem_run.py validate-receipt G3 --strict
```

冻结 N17 计划：

```bash
python .codex/hooks/bridge_fem_run.py freeze-independent-plan \
  .bridge-fem/runs/RUN-001/artifacts/N17/independent_check_plan.json
```

关闭 run：

```bash
python .codex/hooks/bridge_fem_run.py close --reason completed
```

## 6. Gate receipt

每个 Gate receipt 至少包含：

- project、run、node、Gate 和 Skill 名称/版本/哈希；
- 强制条件总数、执行数、通过数、失败数、未实现数和 N/A 数；
- 每条条件的 checker、输入工件、阈值、观测值和证据引用；
- CRITICAL conflict、orphan、未批准高敏感假定和 blocking issue；
- 独立 validator 的 ID、版本、哈希和 `deterministic=true`；
- 全部规定工件的相对路径与 SHA-256；
- 规定审批角色及其绑定工件哈希。

Schema 位于 `.codex/hooks/gate_receipt.schema.json`。

## 7. 当前边界

仓库已经具备生命周期 Hook、节点策略、Gate receipt 结构验证、solver/release barrier 和审计日志。各节点具体工程判据的确定性 validator、独立 Gate evaluator 与 release builder 仍需逐项实现。在它们完成前，未实现条件应写入 receipt 并形成 `BLOCKED`。

Codex Hook 仍有以下边界：

- Hosted WebSearch 等 hosted tools 不经过本地 tool hook；
- 部分专用工具路径可能跳过默认 hook；
- `PostToolUse` 只能发现已经发生的副作用，无法撤销；
- Hook 不能证明工程判据本身写对，确定性 validator 和独立复核仍然必需；
- 用户关闭 Hooks、拒绝信任项目配置或直接在 Codex 外运行命令时，仓库 Hook 无法拦截。

正式项目还应使用只读契约目录、受控执行账户、CI Gate 校验和发布签名作为第二道边界。
