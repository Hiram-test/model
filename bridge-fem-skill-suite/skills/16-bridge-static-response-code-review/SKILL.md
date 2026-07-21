---
name: bridge-static-response-code-review
description: >
  将已通过解验证的桥梁或猫道有限元结果转换为可审查的响应包络，并按项目冻结的正式规则包执行位移、内力、应力、索力、支承反力、构件与截面验算。
  当需要从 verified result set 形成工程判定、定位控制组合、识别模型外局部验算或生成规范复核矩阵时使用。
---

# 任务

你负责把已验证的数值结果转化为工程复核结论。该节点必须保持“结果提取、作用效应、抗力计算、利用率判定、例外处置”五个层次彼此可追溯。所有规则来自节点 01 冻结并批准的 standards manifest 与 rule pack。

# 输入契约

必须读取：

- analysis charter、use cases、response metric register 与 acceptance criteria；
- standards manifest、正式标准文件哈希和经批准的 machine rule packs；
- verified result set、solution verification report 与结果字段映射；
- abstraction decisions、构件分组、模型适用边界和局部细节排除项；
- component inventory、FEM 对象映射、材料、截面、连接和支承属性；
- load plan、combination plan、stage plan 与情景定义；
- 高敏感 assumption、issue register 和前序 gate 限制。

只有 `verified_result_set` 内明确放行的字段可以用于本节点。未经解验证的数据不得通过复制、人工读取截图或二次导出绕过该限制。

# 输出工件

- `response_envelopes.json`；
- `result_extraction_manifest.json`；
- `design_check_matrix.json`；
- `capacity_calculation_ledger.json`；
- `governing_case_register.json`；
- `model_external_check_register.json`；
- `exception_register.json`；
- `static_review_summary.json`。

# 角色边界

本节点可以：

- 提取并包络经验证的位移、反力、截面力、壳合力、应力、应变、索力和连接作用；
- 调用批准的确定性规则引擎完成作用效应与抗力计算；
- 标识控制构件、控制截面、控制阶段、控制组合和控制情景；
- 形成整体模型可支持的通过、边界通过或阻断结论；
- 将焊缝、螺栓群、孔壁承压、局部屈曲、锚具细节等模型外检查移交给专门计算。

本节点不得：

- 依据记忆补写条文、系数、限值或材料强度；
- 将未经批准的经验公式混入正式 rule pack；
- 把节点平均应力、平滑云图或奇异峰值直接当作构件设计值；
- 用单个“最大值”覆盖正负号、方向、阶段和组合差异；
- 将整体杆系或壳模型的结果扩张为未建模局部细节结论；
- 修改 raw result、verified result 或求解器数据库中的数值。

# 核心数据结构

每个响应记录至少包含：

```json
{
  "responseId": "RESP-000421",
  "metricId": "METRIC-GIRDER-MZ",
  "componentId": "COMP-GIRDER-01",
  "femObjectRefs": ["ELEM-1201", "ELEM-1202"],
  "location": {
    "station": {"value": 125.0, "unit": "m"},
    "sectionCutId": "CUT-GIRDER-S125",
    "coordinateSystemId": "CS-GIRDER-LOCAL"
  },
  "quantity": "bending_moment_y",
  "value": {"value": -2.41e7, "unit": "N*m", "basis": "verified-result"},
  "stageId": "STAGE-SERVICE",
  "combinationId": "COMB-SLS-07",
  "scenarioId": "SCN-BASE",
  "signConventionRef": "SIGN-001",
  "extractionMethod": "section_resultant",
  "resultRef": "VR-009822"
}
```

每项验算至少包含：

```json
{
  "checkId": "CHK-001721",
  "useCaseId": "USE-SERVICE-STATIC",
  "componentId": "COMP-GIRDER-01",
  "limitState": "serviceability",
  "checkType": "vertical_deflection",
  "demandRefs": ["RESP-000421"],
  "capacityRef": "CAP-000811",
  "ruleRef": {
    "rulePackId": "RP-APPROVED-001",
    "ruleId": "RULE-DEFLECTION-014",
    "sourceLocator": "STD-SOURCE-03#page=118&clause=...",
    "rulePackHash": "sha256:..."
  },
  "comparison": "abs(demand) <= limit",
  "utilization": 0.78,
  "decision": "PASS",
  "governingCombinationId": "COMB-SLS-07",
  "governingStageId": "STAGE-SERVICE",
  "assumptionRefs": [],
  "issueRefs": []
}
```

# 不可违反的规则

1. 结果提取规则在读取结果前冻结，包括位置、坐标系、符号、分量、平均方式和包络逻辑。
2. demand 与 capacity 分开计算、分开存储，并在 check matrix 中引用；禁止只保留利用率。
3. 每个验算规则必须绑定批准 rule pack、正式来源定位和哈希。
4. 所有单位换算由确定性程序执行，记录原单位、目标单位和转换版本。
5. 梁、壳、实体、索和连接结果采用与其物理含义匹配的提取方法。
6. 阶段结果不得与未激活构件、不同参考构形或不同累计约定混包络。
7. 正负极值、方向极值、绝对极值和范围值分别定义，禁止互相替代。
8. 对非线性工况，组合方式必须与求解策略一致；不得对不能线性叠加的结果做代数组合。
9. 初始张力、预应力、恒载、阶段累计和增量结果的基准必须明确。
10. 接近限值的结果保留足够有效数字和未舍入值；判定使用未舍入值。
11. 缺失的局部检查进入 model external check register，并说明所需输入、责任人和对发布的影响。
12. 一项强制验算缺数据、缺规则或缺适用条件时，结论进入 `BLOCKED`。
13. 任何人工覆盖都要形成 override record，包含理由、批准人、前后值和影响分析；人工覆盖不能修改源结果。
14. 图表、云图和摘要中的数值必须能回链到 responseId 或 checkId。

# 工作顺序

## 1. 冻结结果提取计划

从 response metric register 生成 extraction manifest。逐项定义：

- 对象集合与 componentId；
- 节点、单元端、积分点、截面切面、壳路径或区域；
- 全局、构件局部、截面局部或索局部坐标；
- 正方向和符号约定；
- 端部偏置、刚域、释放和 eccentricity 的处理；
- 节点值、积分点值、截面合力、面积平均、路径平均或热点外推；
- 极值类型和包络维度；
- 允许参与的 stage、case、combination、scenario 和 mesh level。

extraction manifest 经过 schema 校验和规则完整性检查后锁定。后续修改产生新版本并重跑全部相关提取。

## 2. 校核结果资格

对每个拟用结果确认：

- 存在于 verified result set；
- 对象映射唯一；
- 单位和坐标系已解析；
- 工况、组合、阶段和情景状态完整；
- 结果未被 G13 caveat 排除；
- 提取位置没有跨越断面、铰、材料分界或激活边界。

不合格字段写入 exception register，并从正式包络中排除。

## 3. 生成响应与包络

按 metric 生成原子 response record，再执行包络。至少区分：

- 最大正值、最小负值和最大绝对值；
- 同时性要求下的伴随内力；
- 构件端、跨中、塔底、塔顶、支点、锚固点和控制截面；
- 各施工阶段峰值与最终阶段值；
- 各参数情景峰值；
- 服务状态、承载状态及项目定义的其他状态；
- 索力最大值、最小值、松弛裕度和张力变化；
- 支座最大/最小竖向反力、横向反力、纵向反力、位移和可能抬离；
- 猫道控制挠度、索力、横向位移、门架与锚固作用。

需要伴随效应时，在同一结果帧读取，禁止把各分量独立极值拼接成虚构组合。

## 4. 执行响应 sanity check

在规范验算前检查：

- 总体变形和控制点位移与节点 15 一致；
- 截面内力沿构件分布连续，连接、集中荷载和支承位置的跳变有物理依据；
- 截面切面合力与邻近梁单元内力或自由体结果相容；
- 壳积分后的膜力、弯矩和剪力与整体传力路径相容；
- 索力沿无分布荷载索段的变化符合平衡；
- 支反力包络与全局平衡报告相容；
- 对称和反对称工况仍保持预期特征；
- 量级与独立估算处于同一合理区间。

异常先返回节点 15、12、09 或 11定位，禁止直接进入利用率计算。

## 5. 计算作用效应

根据批准 rule pack 处理：

- 组合与包络选择；
- 有效宽度、截面分类、二阶效应放大或稳定相关效应，若在允许范围内；
- 施工阶段累计、预应力损失或温度基准，若已有批准算法；
- 局部坐标转换、截面最不利点应力恢复；
- 轴力—弯矩—剪力—扭矩相互作用所需 demand vector；
- 疲劳幅、动力放大或稳定结果仅在 charter 明确纳入时处理。

每一步保留中间变量、单位、公式版本和 rule trace。

## 6. 计算抗力或允许限值

capacity ledger 逐项记录：

- 材料设计参数和来源；
- 几何与截面参数来源；
- 有效长度、边界条件、长细比或局部板件参数；
- 抗力分项系数、修正系数与适用条件；
- 施工、腐蚀、温度、疲劳或临时状态修正，若适用；
- 公式输入、中间结果、最终抗力和单位；
- 规则有效域检查。

规则输入超出适用域时，停止该项计算并登记异常。

## 7. 形成设计检查矩阵

矩阵至少按以下维度可筛选：

- component、member、section、connection、support、cable segment；
- use case 与 limit state；
- stage、combination、scenario；
- check type 与 rule；
- demand、capacity、utilization、margin；
- decision、governing case、sourceRefs、assumptionRefs、issueRefs。

判定枚举使用：

- `PASS`：需求满足限值，且证据、规则和适用域完整；
- `PASS_WITH_BOUNDS`：所有批准参数边界内均满足，且边界条件已写入允许用途；
- `BLOCKED`：任何批准边界越限，或强制信息不足；
- `NOT_APPLICABLE`：经 charter 明确排除。

不得使用“仅超出很少”“工程上可接受”等无批准依据的替代判定。

## 8. 处理局部模型外检查

对整体模型无法直接支持的项目，创建 external check item：

- 局部对象与 drawing location；
- 上游 demand vector 和提取规则；
- 需要的局部几何、材料、接触或连接数据；
- 推荐的解析、组件模型或实体子模型方法；
- 规则包与验收标准；
- 责任角色、状态和发布阻断属性。

当该检查属于 charter 的强制范围时，未关闭状态导致 G14=`BLOCKED`。

## 9. 生成控制项与例外清单

对每个结构组给出：

- 最大利用率及其未舍入值；
- 控制截面、阶段、组合、情景和规则；
- 次控制项及与控制项的裕度；
- 对高敏感 assumption 的依赖；
- 模型适用限制；
- 未完成或例外检查。

控制项应能在图纸视图、模型视图和报告表格中使用同一稳定 ID 定位。

# 专项检查提示

## 梁、桁架、拱和塔柱

优先使用截面合力和 approved section properties。检查端部局部峰值是否来自刚域、偏心或约束；需要构件设计时，使用构件轴线、有效长度和真实边界条件。杆系模型不直接给出板件局部屈曲、焊缝热点或孔边应力结论。

## 箱梁与壳模型

定义壳法向、局部 1/2 方向、积分层和结果平均区域。整体截面验算优先由闭合截面切面合力恢复，局部板件验算使用经批准的板带、路径或子模型结果。奇异角点与集中约束附近结果单独登记。

## 悬索桥、斜拉桥与猫道索系

检查索力均为物理允许的拉力状态；对可能松弛的构件报告最小张力和发生阶段。索力、线形和支承反力必须对应同一初始状态情景。索夹、鞍座、锚具、散索鞍和局部弯曲需要专门规则或局部模型时，进入 external check register。

## 支座、伸缩与锚固

同时提取力、位移、转角和接触状态。检查设备允许值的来源、方向定义、正负容量和组合规则。出现抬离、滑移、间隙闭合或摩擦切换时，使用非线性结果路径，禁止用线性组合代替。

## 施工阶段和临时结构

逐阶段检查已激活构件、临时支承、张拉、拆除和体系转换。任何阶段的超限都不能由最终成桥状态通过抵消。猫道施工阶段应覆盖架设、面网与踏板安装、人员设备、抗风索或扶手索状态，以及经 charter 定义的风与温度情景。

# 质量门

G14 通过条件：

1. extraction manifest 已冻结，所有提取对象、位置、坐标、符号和平均方法明确；
2. 正式响应全部来自 verified result set；
3. response envelope 覆盖 charter 要求的全部阶段、组合、情景和指标；
4. demand 与 capacity 完整分离并可复算；
5. 每项规则绑定批准 rule pack、来源定位和哈希；
6. 规则适用域、单位、符号和组合逻辑通过确定性检查；
7. 控制项、伴随效应和未舍入判定可追溯；
8. 模型外强制检查已经关闭，或其阻断影响已明确；
9. 高敏感参数边界内结论一致；
10. exception register 没有未批准的严重项；
11. 摘要、表格和图形与机器工件一致；
12. static review summary 明确允许用途和限制。

任一强制规则、强制验算、关键结果资格或模型外检查缺失时，G14=`BLOCKED`。

# 失败处理

- 结果字段资格失败：返回节点 15；
- 响应量级、平衡或符号异常：返回节点 15，并追溯节点 11、09、08 或 07；
- 规则包缺失或未批准：返回节点 01，禁止临时编写系数；
- 构件映射不唯一：返回节点 05、06 或 07；
- 截面、材料或有效长度证据不足：返回节点 08 或 09；
- 局部行为超出整体模型能力：创建模型外检查，并按 charter 判定是否阻断；
- 情景边界内出现通过与不通过混合：状态设为 `BLOCKED`，交节点 17 做敏感性归因，不能选择较有利情景发布。

# 完成检查

1. 每个控制指标是否有预先冻结的提取规则？
2. 所有正式数值是否来自 verified result set？
3. 是否保留正负、方向、阶段、组合和情景维度？
4. demand、capacity、utilization 和 margin 是否均可独立复算？
5. 每项规则是否有正式来源定位、批准状态和哈希？
6. 是否检查规则适用域、量纲、符号与未舍入判定？
7. 是否避免将独立极值拼成虚构伴随效应？
8. 局部模型外验算是否全部登记并判定发布影响？
9. 控制项能否回溯到图纸、模型对象和原始结果？
10. G14 状态是否与 exception register 和所有强制检查一致？
