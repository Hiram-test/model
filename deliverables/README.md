# 扎青吊桥 CAD 参考模型交付说明

本目录交付的是几何审查模型，不是制造级 CAD、完整 FEM 或设计签认成果。

## 文件

- `Zhaqing_Suspension_Bridge_CAD_Reference_v0.2.FCStd`：保留原 N07 分析参考几何，并增加四类只读详图参考对象。
- `Zhaqing_Suspension_Bridge_CAD_Reference_v0.2.step`：便于通用 CAD 软件查看的交换文件；工程追溯属性以 FCStd 为准。
- `Zhaqing_Suspension_Bridge_Analysis_Reference_v0.1.FCStd`：生成 v0.2 时使用的、已完成尺度回读验证的 N07 基线。
- `zhaqing_n07_fem_geometry_ir.json`：基线模型的米制、求解器无关几何数据。
- `cad_detail_preview.png`：包含新增参考对象的全桥预览。
- `detail_reference_verification.json`：FCStd 关闭重开、STEP 回读、尺寸见证、对象数量和 SHA-256 校验结果。
- `manifest.json`：交付文件清单；`role` 说明用途，`bytes` 记录字节数，`sha256` 用于核对文件是否被改变。

## 本次补入的四类对象

1. 索鞍：加入 `R1420`、`R1450`、`R1560` 原图半径见证弧；三者尚未唯一关联到槽底、槽中心线或板件轮廓，因此不替换现有分析接触过渡线。
2. 主锚碇：加入 `10.50 m × 7.20 m × 7.00 m` 局部包络和 `4.70 m` 锚孔间距见证；左右全局放置仍属于参考定位。
3. 风缆锚碇：加入接口高程 `z=-3.534 m`、下控制高程 `z=-6.534 m` 和候选局部包络；外锚平面坐标仍是有界候选。
4. 索塔与基础：加入塔柱候选截面包络、`z=-4.50 m` 基础控制面、`z=-11.00 m` 桩底控制面和底部 `2.00 m` 入岩见证段；Ⅰ-Ⅰ、Ⅱ-Ⅱ截面归属尚未唯一协调。

所有新增详图对象均标记为 `AnalysisParticipation=NONE`。它们用于发现遗漏、查看位置和继续图纸协调，不会自动成为有限元刚度、质量或边界。

只有 `detail_reference_verification.json` 的总状态为 `PASS`，本目录模型才视为成功生成；这仍不改变上述工程用途边界。
