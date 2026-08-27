# C20 门架铰链连接裁决（TOPPIN ROTX）

日期：2026-08-27
Run：`C20_HINGES_TOPPIN_ROTX_20260827T053427734492Z`  job `cw_C20x_0827t053427`

## 销轴方向（已用 CAD 闭合，不再按 ROTX 口头假设）

CAD `build_full_catwalk_from_drawings.py` 坐标：X 横桥、Y 顺桥、Z 竖向。
ANSYS 坐标：X 顺桥、Y 横桥、Z 竖向。

MD4-07 下销 φ75×295：

```
make_cylinder_between(
    ..._lower_support_pin_phi75x295_MD4_07,
    (post_x, y - 147.5, z + 1500),
    (post_x, y + 147.5, z + 1500),
    37.5)
```

圆柱轴线沿 CAD Y = 顺桥 = **ANSYS X**。释放自由度是 **ROTX**，不是 ROTY。
门架平面是 ANSYS YZ，因此该销允许立柱在门架平面内转动。

MD4-03 上端 A 详图销板同样沿 CAD Y 布置，上销轴线同向。

## 本 run 做的连接

- 下端抱箍：284 条立柱底 CERIG 保持 `ALL`（复核：下端另有抱箍，不得做成自由平行四边形）。
- 上端销：284 条立柱顶 CERIG `ALL` → `UX,UY,UZ,ROTY,ROTZ`（只释放 ROTX）。
- 横通道 1386 条 ALL、索 UXYZ 不改。
- 不加 COMBIN14。若静力负主元/不收敛，下一试才在上端加 ROTX 弹簧。

## 已关闭的负证据

| 变体 | 释放 | 结果 |
|---|---|---|
| 两端自由 ROTY | 568 销 | 节点 2027671 UX=6.3e9，XZ 平行四边形机构 |
| 两端自由 ROTX | 568 销 | 节点 2004350 ROTZ 小主元，负主元 |
| 仅上端自由 ROTY | 284 销 | 重力斜坡不收敛，ABT |
| 两端 ROTY + COMBIN14 K=1e8 | 568 | 静力/80 阶通过，TA1 仍 0.07381（错轴） |

## 为何还要再跑 C20

已完成的 C20 SPRING 释放的是 ROTY（错轴），不能激活门架平面内的四端口软模态。
本 run 按图纸销轴做上端 ROTX 铰、下端刚接，才是 C20 的物理闭合。
