# 自动化实施蓝图

## 1. 运行时组成

生产系统建议由十个相互隔离的服务组成。每个服务只承担一种职责，并通过带版本的数据契约交换工件。

| 服务 | 职责 | 关键控制 |
|---|---|---|
| Source Vault | 保存原始图纸、计算原则、表格、模型和正式标准 | 只读、内容寻址、哈希、权限、病毒检查 |
| Artifact Registry | 保存全部中间工件、版本、依赖和 gate 状态 | 不可变、schema 校验、supersession |
| Workflow Engine | 执行 `workflow.yaml`、条件分支、重试和阻断 | 幂等、状态机、审计日志 |
| Evidence Service | 管理 CAD/PDF/表格证据、定位和跨图关系 | 稳定 ID、sourceRef、置信度、冲突图 |
| Geometry & Property Service | 坐标、拓扑、截面、质量、荷载转换 | 确定性算法、单位库、几何容差 |
| Rule Engine | 执行批准的荷载、组合、抗力和限值规则 | 条文定位、版本哈希、适用域、测试向量 |
| FEM Compiler | 把求解器无关 FEM-IR 编译为目标 deck | capability matrix、双向映射、禁止静默降级 |
| Solver Runner | 在锁定环境中运行求解器 | 版本、许可证、资源限额、日志、原始结果哈希 |
| Verification Service | 执行模型检查、平衡、收敛和独立对比 | 预设阈值、不可跳过检查、机器判定 |
| Report & Release Service | 生成报告、发布包、签名和变更影响 | 数据驱动、claim trace、复现测试 |

## 2. 节点执行协议

每个节点使用同一事务协议：

1. orchestrator 解析直接依赖并冻结 input artifact hashes；
2. 生成 node task package，包含 charter、允许工具、输出 schema、gate 规则和审批要求；
3. Skill 完成工程语义推理，输出 draft artifact 与 issue list；
4. 确定性程序完成公式、几何、单位、引用和 schema 检查；
5. validator 将所有失败转成结构化 issue，禁止仅在日志中记录；
6. gate evaluator 根据硬条件计算状态；
7. 需要签认时创建 approval request，签名绑定 artifact hash；
8. 通过后写入 registry，下游只读取该不可变版本；
9. 失败时依据 issue ownership 返回首个责任节点；
10. 新版本通过 `supersedesArtifactId` 连接，旧版本保留。

示意伪代码：

```text
for node in topological_sort(workflow):
    inputs = registry.resolve(node.requires, run_id)
    assert all(hash_ok(x) and schema_ok(x) for x in inputs)
    task = freeze_task(node, inputs, charter, tool_allowlist)
    draft = execute_skill(task)
    validation = run_validators(node, draft, inputs)
    issues = normalize_failures(validation)
    gate = evaluate_gate(node.gate, draft, validation, issues)
    artifact = seal(draft, input_hashes, gate, toolchain)
    registry.append(artifact)
    if gate == BLOCKED:
        stop_descendants(node)
    elif node.requires_approval:
        require_hash_bound_approval(artifact)
```

## 3. 语义与确定性计算分工

### 由 Skill 承担

- 图纸视图和构件角色理解；
- 跨图对应、冲突解释和证据优先级；
- 传力路径与 component group 划分；
- 四类有限元抽象处置；
- 边界、连接、初始状态和阶段的工程语义；
- 异常原因归类、复核计划和报告叙述。

### 由确定性程序承担

- 文件哈希、版本和格式解析；
- 单位转换、坐标变换、几何交点、投影和公差检查；
- 截面属性、质量、重心、荷载总力和总矩；
- 网格统计、约束矩阵、刚度秩和重复节点检查；
- 求解器 deck 生成、运行、结果解析；
- 残差、平衡、收敛、差异和利用率计算；
- schema、引用、rule pack 和发布包校验。

Skill 生成的任何数值先进入 candidate 字段。只有通过 source/assumption、单位、范围和确定性重算后，才能成为 accepted quantity。

## 4. 数据与存储

### 4.1 内容寻址

原始文件和大型结果使用 SHA-256 作为内容地址。文件名只用于显示，引用使用 `sourceId + hash + locator`。同一内容重复上传时复用存储，同时保留不同业务版本记录。

### 4.2 稳定 ID

ID 由对象类型、项目命名空间和不可变序号构成。几何重生成时尽量通过 source handle 与语义键保持 componentId；网格 elementId 可以变化，但必须维护 `componentId → geometryId → elementSetId` 映射。

### 4.3 坐标与单位

- 内部采用单一单位政策；
- 所有接口数量使用 `{value, unit, basis}`；
- 坐标带 coordinateSystemId；
- 每次转换保存变换矩阵、原值和程序版本；
- 报告显示单位可以变化，机器层保留内部单位和原始单位。

### 4.4 证据定位

CAD 使用 handle、layer、block path、xref、layout；PDF 使用 page、bounding box、viewId；表格使用 sheet/cell/range；图像使用像素区域和标定；规则使用 source hash、page、clause 和 ruleId。

## 5. 求解器适配器

每个求解器适配器声明 capability matrix：

- 支持的单元和自由度；
- 几何与材料非线性；
- tension-only、compression-only、gap、contact、friction；
- 初应变、初应力、无应力长度和找形；
- 施工激活、状态继承和重启动；
- 局部坐标、偏心、刚臂和释放；
- 结果字段、积分位置和符号；
- 版本限制和已知缺陷。

编译过程产生双向 map：`IR object → solver entity` 和 `solver field → IR quantity`。任何 unsupported feature 进入 blocker。适配器发布前需要通过单元测试、解析基准、单元级 patch test、整体验证模型和 round-trip map 测试。

## 6. 规则包治理

正式标准先由专业人员转换为规则包，再进入自动计算。每条规则保存：

- 正式来源文件哈希与定位；
- 适用 jurisdiction、结构类型、材料、极限状态和版本；
- 输入量、单位和有效域；
- 公式表达、分支、舍入与比较方向；
- 测试向量、边界值和已知例外；
- 编制、复核和批准签名；
- 生效、替代和撤回状态。

规则引擎拒绝无批准状态、来源哈希不一致、输入超适用域或单位不兼容的调用。

## 7. 自动化准确性测试体系

### 7.1 单元测试

覆盖解析器、单位、坐标、截面、质量、荷载转换、组合、结果映射、利用率和哈希。每个函数包含正常值、边界值、非法值和量纲错误。

### 7.2 黄金样例

保留一组人工审核的小型模型：

- 简支梁；
- 连续梁；
- 平面桁架；
- 门式框架；
- 壳板 patch；
- 单索悬链线；
- 猫道单跨；
- 斜拉索—梁简化体系；
- 支座弹簧和间隙；
- 多阶段激活/拆除。

每个样例具有解析值或独立权威结果、容差、预期警告和预期 gate。

### 7.3 性质与变形测试

使用不依赖具体数值的性质检查：

- 刚体平移不改变内力；
- 单位等价输入产生相同物理结果；
- 对称模型和荷载产生对称响应；
- 荷载倍增在线性模型中产生同比响应；
- 网格细化后控制 metric 收敛；
- 荷载离散前后总力和总矩守恒；
- 坐标旋转后变换回全局的结果一致；
- 只拉索不出现压缩承载。

### 7.4 回归测试

每次 Skill、schema、parser、solver adapter、rule pack 或求解器版本变化，重跑黄金样例。回归报告区分允许变化、预期数值漂移和异常变化。

### 7.5 交叉验证

高风险用途执行至少一种独立方法。第二求解器需先证明物理能力和结果字段可比；简化模型需预先定义预期差异。交叉对比阈值在运行前冻结。

## 8. 质量指标仪表板

建议持续跟踪：

| 指标 | 含义 | 典型阻断逻辑 |
|---|---|---|
| source coverage | 必需资料已接入比例 | 关键资料缺失阻断 G1 |
| evidence coverage | 已接受事实带来源/假定比例 | 关键事实低于 100% 阻断 |
| unresolved conflict count | 关键跨图冲突数量 | CRITICAL > 0 阻断 G3 |
| orphan component/model object | 无来源或无归属对象 | 关键 orphan > 0 阻断 |
| geometry closure error | 闭合、节点重合、跨径与标高误差 | 超 charter tolerance 阻断 G6 |
| mass discrepancy | 模型质量与独立 ledger 差异 | 超阈值阻断 G7/G11 |
| load resultant discrepancy | 离散前后总力/总矩差异 | 超阈值阻断 G9 |
| constraint health | 机构、过约束、孤立自由度 | 严重项阻断 G11 |
| equilibrium residual | 全局与自由体平衡误差 | 超阈值阻断 G13 |
| convergence delta | 粗/细网格控制量差异 | 超阈值阻断 G13 |
| independent difference | 主模型与独立计算差异 | 超阈值且无法解释阻断 G15 |
| bound decision flips | 参数边界内判定翻转数 | 大于 0 阻断 G15 |
| claim trace coverage | 关键结论端到端可追踪比例 | 低于 100% 阻断 G16 |
| reproducibility status | 干净环境复现状态 | 失败阻断 G16 |

阈值来自 analysis charter 和批准验证计划，不在平台代码中写死通用工程阈值。

## 9. 人工签认点

推荐保留四个强制签认：

1. G0：分析负责人批准 intended use、规范、验收标准和风险等级；
2. G5：分析负责人批准抽象、边界情景和模型能力；
3. G9：分析负责人批准荷载、组合和施工阶段；
4. G15/G16：独立检查人和批准人确认工程结论、可信度、限制与发布。

G3 的关键图纸冲突采用按需签认。签认通过系统审批完成，签名绑定工件哈希，不能用聊天中的默认同意代替。

## 10. 安全与运行隔离

- 上传文件在隔离环境解析，禁用宏、脚本和外部链接；
- 求解器以最小权限运行，限制 CPU、内存、磁盘和网络；
- CAD/PDF 解析器使用固定版本和沙箱；
- 凭据、许可证和私有标准通过受控秘密管理注入；
- 所有命令、文件写入、网络访问和工具版本进入审计日志；
- 发布包做恶意文件和敏感信息扫描。

## 11. 首个项目落地顺序

### 阶段 A：只读证据链

先实现 N01–N06，不生成正式求解 deck。用一个已完成项目验证图纸接入、跨图冲突、component inventory 和抽象结果，建立人工基准。

### 阶段 B：单一求解器闭环

实现 N07–N16，选一个结构体系和有限工况。优先完成确定性几何、质量、荷载、平衡与结果映射，限制求解器能力范围。

### 阶段 C：猫道/索系分支

启用 N10 的找形、初态和施工阶段，建立悬链线与猫道黄金样例，并加入 tension-only、温度和锚固反力检查。

### 阶段 D：独立保证与发布

实现 N17–N18、第二方法、敏感性、可信度、签名和可复现发布包。此阶段完成后再把系统用于正式工程决策。

### 阶段 E：扩桥型与规则包

按桥型、材料和 jurisdiction 逐步扩展。每次只加入经过基准测试和专业批准的能力，capability matrix 同步更新。
