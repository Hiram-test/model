# 扎青吊桥 CAD-003 FreeCAD 虚拟机建模

本目录把“读取图纸证据 → 冻结数值 → FreeCAD 建模 → STEP 回读 → 视图保存”拆成确定性步骤。低推理强度模型只能修改待审查的 `source_facts.json` 或提交新的上游证据，不能在 FreeCAD 脚本中直接填尺寸。

## 文件与职责

| 文件 | 职责 |
|---|---|
| `source_facts.json` | 指定每个控制事实的源文件、CAD 句柄、字段、单位和冻结检查。 |
| `freeze_model_contract.py` | 从 N03 CSV 唯一解析事实，闭合 82m、5+72+5m、550=470+40+40cm 等尺寸链。 |
| `build_freecad_model.py` | 7 个明确阶段建立骨架、桥面梁系、塔、索系、锚碇和风缆，并保存阶段 FCStd。 |
| `validate_freecad_model.py` | 独立打开 FCStd/STEP，检查对象数、形状、元数据、重复体、包围盒和 STEP round-trip。 |
| `render_freecad_model.py` | 在 Xvfb 中由 FreeCAD GUI 保存轴测、立面、平面和横断面图。 |
| `run_freecad_pipeline.sh` | fail-closed Hook；按固定顺序运行并封装脚本、日志、模型和校验记录。 |

## 建模阶段

1. `01_reference_skeleton`：桥轴、27 道横梁站点、左右索面和控制点；不导出 STEP。
2. `02_deck_system`：27 道横梁、52 段纵梁、78 块桥面板。
3. `03_tower_foundations`：两座双柱塔、塔顶横梁、承台和 8 根显示桩。
4. `04_cable_system`：4 个索鞍、2 条主缆、50 根吊杆。
5. `05_main_anchorages`：两座主缆锚碇控制外包络。
6. `06_wind_system`：4 条精确 21.91m 风缆和 4 座候选风缆锚碇。
7. `07_save_export`：保存 FCStd、导出 STEP、对象清单和构建过程。

## 状态边界

技术模型可以通过 FreeCAD/STEP 回读，但工程 Gate 仍保持 `BLOCKED`：

- 风缆锚碇平面坐标允许随地形调整，当前没有唯一测量坐标；
- 塔基础桩长和承台底标高未由地质资料闭合；
- 主缆进入锚碇的精确三维接口未完成回投；
- 制造 Part 全覆盖、装配图、传力路径和全部 N04 overlay 工件尚未闭合。

因此输出只用于整体装配查看、STEP 交换测试和后续 FEM 几何接口开发，不得用于施工放样、加工、工程量或正式结构计算。
