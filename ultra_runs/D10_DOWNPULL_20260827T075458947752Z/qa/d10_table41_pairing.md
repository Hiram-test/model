# D10 与附件2-3表4-1物理模态配对

配对依据振型物理特征（有效质量方向、两幅猫道同/反相、主跨正/反对称、SENE 组件占比），
禁止仅按频率阶次硬配。门架上端释放 ROTX 产生的平面内局部模态单独列出，不进入表4-1。

D10 官方 `*GET MODE,PFACT/EFFM` 在 POST1 读 RSTP/MODE（RESUME eq.db 之前）成功，LS1 EY=1753 t 与 S10 同频阶一致。
RSTP 展开 **80/80**。与 C20 交叉复查后的阶次一一对应，Δf < 4e-5 Hz。
TA1 仍是 M3=0.07337 Hz（与 LA 杂交，−26%），不得改配到 M6 正对称扭转。

| 表4-1 | 说明 | 实测 Hz | FEM 阶 | FEM Hz | 偏差 | 配对依据 |
|---|---|---:|---:|---:|---:|---|
| LS1 | 一阶正对称横弯 | 0.0365 | 1 | 0.036826 | +0.89% | family=L symmetry=S shareL=1.000 shareV=0.000 shareT=0.000 EY=1.75e+03 EZ=5.5e-10 ERX=4.38e+13 ERY=923 gateSENE=0.340 cableSENE=0.646 sideRatio=0.00 |
| VA1 | 一阶反对称竖弯 | 0.0700 | 2 | 0.071525 | +2.18% | family=V symmetry=A shareL=0.000 shareV=1.000 shareT=0.000 EY=2.93e-12 EZ=5.52e-06 ERX=15.6 ERY=6.19e+14 gateSENE=0.077 cableSENE=0.882 sideRatio=0.00 |
| LA1 | 一阶反对称横弯 | 0.0726 | 4 | 0.073782 | +1.63% | family=L symmetry=A shareL=0.572 shareV=0.006 shareT=0.422 EY=1.12e-08 EZ=3.56e-10 ERX=3.01e+05 ERY=1.16e+03 gateSENE=0.838 cableSENE=0.150 sideRatio=0.00 |
| TA1 | 一阶反对称扭转 | 0.0996 | 3 | 0.073369 | -26.34% | family=T symmetry=A shareL=0.490 shareV=0.008 shareT=0.503 EY=6.22e-08 EZ=3.91e-11 ERX=2.09e+05 ERY=2.11e+07 gateSENE=0.804 cableSENE=0.183 sideRatio=0.00 |
| VS1 | 一阶正对称竖弯 | 0.1028 | 5 | 0.101271 | -1.49% | family=V symmetry=S shareL=0.000 shareV=1.000 shareT=0.000 EY=5.1e-07 EZ=140 ERX=9.11e+04 ERY=4.8e+14 gateSENE=0.001 cableSENE=0.998 sideRatio=0.00 |
| LS2 | 二阶正对称横弯 | 0.1087 | 7 | 0.110280 | +1.45% | family=L symmetry=S shareL=0.999 shareV=0.000 shareT=0.001 EY=197 EZ=1.45e-07 ERX=2.02e+13 ERY=4.99e+05 gateSENE=0.314 cableSENE=0.683 sideRatio=0.00 |
| TS1 | 一阶正对称扭转 | 0.1147 | 6 | 0.103371 | -9.88% | family=T symmetry=S shareL=0.012 shareV=0.015 shareT=0.973 EY=0.279 EZ=3.94e-06 ERX=1.81e+11 ERY=1.41e+07 gateSENE=0.016 cableSENE=0.984 sideRatio=0.00 |
| SIDE1 | 边跨模态1（附件未细分） | 0.1149 | 8 | 0.116225 | +1.15% | family=SIDE symmetry=NA shareL=0.553 shareV=0.099 shareT=0.086 EY=553 EZ=1.32e-12 ERX=2.62e+13 ERY=2.63 gateSENE=0.802 cableSENE=0.198 sideRatio=1.00 |
| SIDE2 | 边跨模态2（附件未细分） | 0.1239 | 9 | 0.124857 | +0.77% | family=SIDE symmetry=NA shareL=0.067 shareV=0.191 shareT=0.311 EY=526 EZ=4.01e-11 ERX=1.84e+13 ERY=16.9 gateSENE=0.852 cableSENE=0.147 sideRatio=1.00 |
| VA2 | 二阶反对称竖弯 | 0.1438 | 12 | 0.145407 | +1.12% | family=V symmetry=A shareL=0.000 shareV=1.000 shareT=0.000 EY=3.71e-09 EZ=1.47e+03 ERX=7.74e+04 ERY=5.07e+15 gateSENE=0.000 cableSENE=1.000 sideRatio=0.00 |
| LA2 | 二阶反对称横弯 | 0.1449 | 25 | 0.220265 | +52.01% | family=L symmetry=A shareL=0.985 shareV=0.001 shareT=0.014 EY=0.000119 EZ=1.85e-12 ERX=1.58e+07 ERY=4.71e+07 gateSENE=0.863 cableSENE=0.132 sideRatio=0.00 |
| SIDE3 | 边跨模态3（附件未细分） | 0.1557 | 17 | 0.165882 | +6.54% | family=SIDE symmetry=NA shareL=0.279 shareV=0.078 shareT=0.215 EY=1.29e-08 EZ=427 ERX=2.83e+04 ERY=9.1e+13 gateSENE=0.001 cableSENE=0.999 sideRatio=1.00 |
| TS2 | 二阶正对称扭转 | 0.1571 | 16 | 0.149643 | -4.75% | family=T symmetry=S shareL=0.005 shareV=0.015 shareT=0.980 EY=3.5e-06 EZ=8.34e-09 ERX=1.59e+06 ERY=3.42e+06 gateSENE=0.693 cableSENE=0.281 sideRatio=0.00 |
| VS2 | 二阶正对称竖弯 | 0.1744 | 21 | 0.187523 | +7.52% | family=V symmetry=S shareL=0.000 shareV=1.000 shareT=0.000 EY=6.12e-07 EZ=286 ERX=9.83e+04 ERY=9.84e+14 gateSENE=0.005 cableSENE=0.994 sideRatio=0.00 |

## 排除的门架 ROTX 局部模态

| 阶 | Hz | toppost SENE | cable SENE | 说明 |
|---:|---:|---:|---:|---|
| 27 | 0.223428 | 0.847 | 0.020 | LOCAL_GATE_ROTX |
| 28 | 0.225203 | 0.848 | 0.017 | LOCAL_GATE_ROTX |
| 31 | 0.231493 | 0.865 | 0.022 | LOCAL_GATE_ROTX |
| 32 | 0.231691 | 0.852 | 0.021 | LOCAL_GATE_ROTX |
| 34 | 0.240851 | 0.852 | 0.022 | LOCAL_GATE_ROTX |
| 35 | 0.248323 | 0.887 | 0.012 | LOCAL_GATE_ROTX |
| 37 | 0.251704 | 0.844 | 0.010 | LOCAL_GATE_ROTX |
| 42 | 0.258166 | 0.878 | 0.036 | LOCAL_GATE_ROTX |
| 45 | 0.265880 | 0.852 | 0.006 | LOCAL_GATE_ROTX |
| 46 | 0.267663 | 0.880 | 0.033 | LOCAL_GATE_ROTX |
| 47 | 0.273692 | 0.851 | 0.013 | LOCAL_GATE_ROTX |
| 49 | 0.287401 | 0.853 | 0.005 | LOCAL_GATE_ROTX |
