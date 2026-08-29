# 扎青吊桥 CAD-003：Ubuntu 虚拟机 FreeCAD/STEP 建模说明

## 1. 本目录解决什么问题

本目录不是“把几张图画成一座看起来像桥的三维模型”，而是把 12 张冻结 DWG 按以下顺序变成可追溯的 FreeCAD 与 STEP 工件：

```text
原始 DWG
→ SHA-256 与只读转换记录
→ DXF 实体、文字、尺寸和句柄索引
→ N04–N06 数值/装配/抽象契约
→ FreeCAD 权威参考几何 + 非权威显示实体
→ FCStd 与 STEP
→ 新进程重新打开 FCStd、重新导入 STEP
→ 独立几何/哈希/数量/拓扑检查
```

所有运行都在一次性的 Ubuntu 24.04 GitHub Actions 虚拟机内完成。失败输出会先上传，再让工作流报错，避免失败过程被删除。

## 2. 工程状态边界

CAD-003 的用途是：**图纸证据绑定的总体参考几何与 FEM 抽象准备模型**。

它不是：

- 加工下料模型；
- 施工放样模型；
- 局部连接、焊缝或螺栓实体模型；
- 已找形并完成结构计算的生产模型；
- 工程安全放行结论。

`U-WIND-001` 仍未关闭：风缆长度、直径、角度限制及桥面端位置可由图纸读取，但四个风缆锚碇的测量平面坐标不能从现有图纸唯一确定。因此模型只建立有明确标签的候选位置，整体工程发布状态保持 `BLOCKED`。

## 3. 每一步脚本与工件

| 阶段 | 脚本 | 主要动作 | 过程记录 |
|---|---|---|---|
| N02/N03 | `scan_drawings.py` | 计算 DWG 哈希，LibreDWG 只读转换，提取文字、尺寸、实体和布局 | `scan/runner.log`、`scan_report.json`、转换日志 |
| N03 | `render_and_export_dxf.py` | 导出带 source/layout/handle 的完整几何 JSONL；生成初始渲染 | `n03-geometry-runner.log`、`geometry_export_report.json` |
| N03 健康检查 | `manual_render_geometry.py` | 从序列化几何直接黑线白底重画 12 张 Model Space，并检查非白像素 | `n03-manual-render.log`、`manual_render_report.json` |
| N04–N06 | `compile_model_contract.py` | 按固定句柄读取数值，执行尺寸链复算，生成构件计数、装配图、representation contract 与不确定性登记 | `04-contract.log`、`contract_compile_record.json` |
| N07 建模 | `build_freecad_model.py` | 在 FreeCADCmd 中建立参考线/中面/接口与显示实体，保存 FCStd、导出 STEP | `06-freecad-build.log`、`freecad_build_journal.json`、`freecad_build_manifest.json` |
| N07 独立检查 | `validate_freecad_model.py` | 在第二个 FreeCADCmd 进程中重新打开 FCStd、重新导入 STEP，复核哈希、数量、稳定 ID、形状有效性、装配可达性和包围盒 | `07-independent-validation.log`、`n07_geometry_validation.json`、`validator_receipt.json` |
| 总控记录 | `run_vm_freecad_pipeline.sh` | 逐阶段执行，记录命令、起止时间、用时、退出码、日志路径；失败关闭 | `stage_ledger.jsonl`、`process/logs/` |
| 汇总 | `generate_run_report.py` | 无论成功或失败都生成中文过程报告和全部文件 SHA-256 | `VM_BUILD_RECORD.md`、`artifacts_sha256.json` |

## 4. FreeCAD 文档分层

生成的 `Zhaqing_CAD-003.FCStd` 使用以下对象组：

- `G00_SourceEvidence`：项目、坐标系、契约哈希、阻断原因；
- `G10_AuthoritativeReferenceGeometry`：梁/索中心线、板中面、锚固和索鞍接口点；
- `G20_DisplaySolids`：便于查看和 STEP 交换的实体外形；
- `G30_InterfaceNodes`：有限元接口节点登记的紧凑几何表示；
- `G40_BoundedConstructionCandidates`：尚未关闭的有界候选与限制。

显示实体不会反向成为工程事实。例如主缆实体直径由钢丝总面积换算，仅供显示；锚碇内部构造未在现有证据中闭合，因此只生成外包络，不虚构内部台阶或钢筋。

## 5. 确定性防错规则

1. 12 张图纸必须全部转换成功；少一张即停止。
2. 关键数值必须匹配唯一的 `图名 + layout + entity type + handle`；零条或多条即停止。
3. 吊杆 25 个长度必须与表格顺序完全一致；第 17 根使用句柄 `373B`，不得误读相邻站号。
4. 主跨、吊杆区、塔宽、桥宽和吊杆下端标高必须通过独立公式闭合。
5. 构件计数由契约固定；FreeCAD 保存后重新统计，不能信任 builder 自报。
6. FCStd 和 STEP 都保存 SHA-256；STEP 必须在独立文档中重新导入且包围盒与 FCStd 一致。
7. 构件稳定 ID、来源引用和 representation 不能为空。
8. `BLOCKED` 状态写入契约、FCStd 元数据和构建清单；几何检查通过不能清除该状态。
9. builder 和 validator 都声明 `gateAuthority=false`；它们不能自行宣布工程 Gate 通过。

## 6. 在本地兼容环境复现

虚拟机流水线是正式复现入口。具备 FreeCADCmd、LibreDWG 和 Python 3.11 环境时，也可运行：

```bash
automation/zhaqing_cad003/run_vm_freecad_pipeline.sh \
  build/zhaqing-cad003/scan \
  build/zhaqing-cad003/run
```

最终关键文件位于：

```text
build/zhaqing-cad003/run/
├── contract/model_contract.json
├── model/Zhaqing_CAD-003.FCStd
├── model/Zhaqing_CAD-003-display.step
├── model/fem_geometry_ir.json
├── validation/n07_geometry_validation.json
└── process/VM_BUILD_RECORD.md
```
