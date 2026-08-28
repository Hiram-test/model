# 工坊 2 · 极端工况与图谱

性质：本轮扫掠 + 主曲线回填。不是科学结论。

## 2.1 工况库

43 项已入库。龙卷 / 下击暴流 / derecho 在扫掠表标 `stationarity=reference_only`，图上打叉或斜纹。C 级 15 项未在线复核，保留角标。〔待填:C 级复核清单逐条〕

## 2.2 主曲线连续图谱

脚本 `code/master_surface.py`。规则 (U10, Iu) 网格上直算四通道跨最大，再双线性插值。43 个命名事件是曲面上的投影点。

交叉验证门：平稳事件四点相对误差 < 5%。结果见 `artifacts/atlas/master_surface_cv.json`。不过门修方法，不放宽。

P16/P84 气动不确定度带：〔待填:CdD 区间尚未做集合〕。v0 曲面是 P50 网格。

## 2.3 图谱产品

| 图 | 文件 | 状态 |
|---|---|---|
| A1 | `atlas/heatmap_scenarios.png` | 已出 |
| A2 | `atlas/alongspan_family.png` | 已出 |
| A3 | `atlas/survival_frontier.png` | 已出；利用率通道未做（无重建索力） |
| A4 | `atlas/comparison_attach23.png` | 已出；三点不是全曲线数字化 |
| A5 | `atlas/A5_master_surface.png` | 本轮补 |

每图脚注 deck sha + 气动版本。
