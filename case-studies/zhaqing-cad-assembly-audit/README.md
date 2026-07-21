# 扎青吊桥关键装配图纸与模型

## 目的

本目录保存扎青吊桥 CAD 自动化案例中用于复核关键装配错误的原始 DWG，以及产生问题的 CAD-001 和经过实体穿透修正的 CAD-002 模型。

这些文件用于复现和改进 Bridge FEM Skill Suite 的 N04–N07 工作流，不代表工程放行成果。

## 重要状态声明

- `CAD-001` 是错误暴露版本，存在完整装配副本重合和 450 对非设计意图实体穿透。
- `CAD-002` 消除了重复、孤立和实体穿透，但未完成真实图纸坐标回投、装配图、传力路径和 FEM representation contract。
- CAD-002 的原 `G6=PASS_WITH_BOUNDS` 结论已经撤回；严格状态应为 G3–G6 `BLOCKED`。
- 两个版本均不得用于结构计算、施工放样、加工下料、工程量或安全结论。

完整复盘见仓库根目录的 [`ZHAQING_CAD_SKILL_LESSONS.md`](../../ZHAQING_CAD_SKILL_LESSONS.md)。

## 目录结构

```text
case-studies/zhaqing-cad-assembly-audit/
├── drawings/          # 复核关键装配关系的原始 DWG
├── models/CAD-001/    # 初始错误模型，包含 FCStd 与 STEP
├── models/CAD-002/    # 消除实体穿透后的模型，仍未通过工程装配门禁
└── README.md          # 文件范围、状态和哈希说明
```

## 图纸与问题对应关系

| 图纸 | 主要复核内容 |
|---|---|
| `01-扎青桥总体布置1.dwg` | 主跨、边跨、塔位、锚点和总体标高关系 |
| `03-缆索布置.dwg` | 主缆索面、线形、塔顶和锚固关系 |
| `04-05-桥面板构造.dwg` | 桥面板范围、厚度及与梁系关系 |
| `06-11-横梁构造.dwg` | 横梁位置、吊点接口和桥面横向传力 |
| `12-纵梁构造.dwg` | 纵梁位置、截面和塔端支承关系 |
| `14-吊杆布置.dwg` | 吊杆站点及吊杆与主缆、横梁的装配关系 |
| `19-索塔一般构造.dwg` | 塔柱、塔梁、基础、桥面和索鞍位置 |
| `26-锚碇一般构造.dwg` | 锚点标高、锚室和主缆端部装配 |
| `29-索鞍构造.dwg` | 索鞍中心、鞍槽和主缆通过关系 |
| `32-风缆构造.dwg` | CAD-002 遗漏的横向稳定索系 |
| `33-风缆锚碇.dwg` | 风缆锚固及横向传力终点 |
| `桥跨横断面图.dwg` | 桥宽、纵梁间距、主缆索面和吊点横向坐标 |

## 已确认的模型问题

### CAD-001

- 保存了与全部语义构件同位的完整装配导出体；
- 纵横梁、塔柱、塔梁、索鞍、主缆、吊杆等通过体积搭接表达连接；
- 376 个语义构件实体中检测到 450 对非设计意图穿透。

### CAD-002

- 吊杆下端接触桥面板顶面，没有建立横梁端部或加劲梁吊点接口；
- 风缆、抗风吊杆和风缆锚碇未建模，横向传力路径不完整；
- 锚点标高、锚碇外形、塔柱、承台和桩基包含展示假定；
- 主缆为指定抛物线，不是找形后的平衡线形；
- 主缆索面、索鞍、塔柱和桥面横向位置没有真实 DWG overlay 证据；
- 支承、索夹、吊杆连接件、锚固接口和偏心关系尚未定义。

## 后续使用方式

1. 先用 N04 对平面、立面、横断面和节点详图建立坐标变换与回投 overlay；
2. 用 N05 建立 `assembly_graph`、`load_path_graph` 和 orphan audit；
3. 用 N06 冻结参考线、中面、偏心、连接、支承和初始状态；
4. 新建 CAD-003，不覆盖 CAD-001 或 CAD-002；
5. 用 N07 逐实例检查 required interface、forbidden penetration、forbidden contact 和图纸回投；
6. 原生 G3–G6 全部通过后，才允许进入材料、荷载、网格和求解节点。

## SHA-256 文件清单

| 文件 | SHA-256 |
|---|---|
| `drawings/01-扎青桥总体布置1.dwg` | `D32D8272ECDAD043E6FB42B8310E8E7C7BDE77CDCACA79AA5976735DEDDA5E36` |
| `drawings/03-缆索布置.dwg` | `69BC75E93CB2D00734D259F98D522C38BEA9926BB92AC0D2B35109BF9C0B44A0` |
| `drawings/04-05-桥面板构造.dwg` | `D768F812697AD4A94AB8EA99B622148D21352936905C6B6400128D5BD7C5D11C` |
| `drawings/06-11-横梁构造.dwg` | `FB59CCE7C33B879DC98487CFD8CD4E2B7D110F6A3ADB86A94EA50696266B7258` |
| `drawings/12-纵梁构造.dwg` | `F64F9409FFD74469C0902851B3E2CE754E4B3DF6E539F8DD11837864BD005681` |
| `drawings/14-吊杆布置.dwg` | `74ADE48587C900FB6F6DB78C173B84DD9EB9DCA132BA38087CB069BEC99F746C` |
| `drawings/19-索塔一般构造.dwg` | `C0ECADBE1DC2AC98C30D3E21C83170AC3536A67FB17F3F5A5EED662FE7C516A1` |
| `drawings/26-锚碇一般构造.dwg` | `9C2B9EDFB52430F2F9AF49CE37ED8E63F3CC7A57A70FF9123BBBE2220A4AA771` |
| `drawings/29-索鞍构造.dwg` | `D9230DD923C25A586BDA49A5BD804992E26006BAA53CB96876D9A38A4CDA7B4E` |
| `drawings/32-风缆构造.dwg` | `D6E3FD15D4CE185B369194F09AE389D87594615F787A9FA6509B2B02EFD23F7F` |
| `drawings/33-风缆锚碇.dwg` | `59EC1A9891E6E261CE2A4BB11EAE26497C6EDC88B08EF5D3221E74E16759CF41` |
| `drawings/桥跨横断面图.dwg` | `C555390F2EE8CDD924219A45D48D1F15FDC37D802F066BAC3D6290A7EE2B64DF` |
| `models/CAD-001/zhaqing_suspension_bridge_82m_skill_cad.FCStd` | `5AF16EE59A2B2F3DE978785E54038F47CF3520D188BB7BB6D514F3A7EF04E539` |
| `models/CAD-001/zhaqing_suspension_bridge_82m_skill_cad.step` | `450BD1E41A381EC69ACC58812B4B9006D9FB7FBBC718C3F9DBD814AD2D3428B5` |
| `models/CAD-002/zhaqing_suspension_bridge_82m_skill_cad.FCStd` | `DBB69BEE2AE9C7A86E5F87CF16B7E93DC7510AC3E3BECFE87E65FB8EA276919C` |
| `models/CAD-002/zhaqing_suspension_bridge_82m_skill_cad.step` | `75C9ECE14C6A6F0F368EC034663A5E89FEA7AAABEF5BF47E506477EAC478561A` |
