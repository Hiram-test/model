# 真实三维猫道 · 全球极端风工况扫掠 —— 实验方案与执行架构

**本目录只交付方案、架构与工况库；不含任何已完成的求解结果。计算由外部执行者按
`code/run_solver.sh` → `buffeting.py` → `sweep_extreme.py` → `make_atlas.py` 顺序执行。**

方案正文：`report/true3d_extreme_experiment_plan_cn.pdf`

## 一句话说明

以 main 分支封板的 S10 V2.0 真实三维 ANSYS 模型（109,086 节点 / 172,994 单元，
附件 2-3 对齐版，700 MB `.db` 与 77 MB STEP 在 release
`catwalk-attachment23-v2.0-s10-20260716`）为唯一几何/初应力权威源，按 R1–R7 简化契约
移植为 ~7k 单元的 CalculiX 真实三维模型（每幅两条步道带、门架/横通道真实截面、
±21.4 m 全宽扭转拓扑），完成静力+摄动模态后，用准定常抖振谱方法输出附件 2-3 型的
**抖振 RMS 沿跨分布**，再把 43 项全球极端风工况全部扫掠成响应图谱。

## 目录

| 路径 | 内容 | 状态 |
|---|---|---|
| `code/parse_s10.py` | S10 十一个 include 的解析器（44 索线/横梁排/门架/通道/质量/初应力/约束） | 已验证跑通（pod 崩溃前）|
| `code/build_true3d_ccx.py` | R1–R7 简化建模器 → `solver/true3d_ccx.inp` | 写毕待执行 |
| `code/run_solver.sh` | S1–S5 求解链 runbook + 四道 gate（G-P1..P4） | 待执行 |
| `code/postprocess_modes.py` | FRD→模态基（L/V/幅内扭/全局扭分类；表 4-1 锁定规则接口） | 待执行 |
| `code/buffeting.py` | Kaimal+Davenport 准定常多模态抖振谱（式与量纲全给定） | 待执行 |
| `code/sweep_extreme.py` | 43 工况全扫掠 + 非平稳工况降级标注 | 待执行 |
| `code/make_atlas.py` | 图谱 A1–A4（热图/沿跨族/生存边界/附件对照） | 待执行 |
| `config/site_wind.json` | 桥址/湍流/气动/阻尼参数（含"待从附件 2-3 提取"清单） | 定稿 |
| `artifacts/extreme_weather_library.{json,md}` | 43 项工况库（A/B/C 置信分级+口径换算） | 定稿 |
| `report/` | 实验方案 PDF/TeX | 定稿 |

## 执行者需要补的三个外部输入

1. **附件 2-3 气动参数与 RMS 目标图**：
   release `zhangjinggao-full-20260729` 的 `archive-0001.tar.zst` 内
   `01_设计资料与规范/附件2-3：猫道结构抗风性能试验报告.pdf`（3.19 MB，
   sha256 d17d4061…）。提取三分力系数与设计风速填入 `config/site_wind.json`，
   RMS 图数字化为 `artifacts/attach23_rms_digitized.csv`。
2. **承重索破断力**（图纸）：填 `config.structure.rope_break_force_kN_per_bearing_rope`，
   解锁图谱 A3 的承载率通道。
3. **C 级工况在线复核**（工况库 md 有清单），或保留"未复核"标注出图。

## 已知求解器陷阱（上一轮 agentic-fea 已二分定位，本链已内建规避）

1. `TYPE=MASS` × `*FREQUENCY,PERTURBATION` → `add_bo_st` 致命错 ⇒ 质量折密度分箱（R6）。
2. T3D2 膨胀自旋伪模态 ⇒ 索用 B31 等积方形截面（R1）。
3. SPC 反力迁移膨胀 knot ⇒ 反力核验走全场合力。
4. BOX 截面仅限 B32R ⇒ 全部 RECT 等效（惯矩双向匹配，`rect_match`）。

## 环境备注

本 VM（4 核 15 GB）在 2026-08-28 06:5x–08:1x 之间三次非自愿重启（pod 级终止，
与脚本无关，其中一次发生在完全空闲时）。因此本链每个阶段产物都要求即时 commit；
执行者若用同类环境请照做。
