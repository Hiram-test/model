# C20 与附件2-3表4-1物理模态配对

配对依据振型物理特征（有效质量方向、两幅猫道同/反相、主跨正/反对称、SENE 组件占比），
禁止仅按频率阶次硬配。门架上端释放 ROTX 产生的平面内局部模态单独列出，不进入表4-1。

| 表4-1 | 说明 | 实测 Hz | FEM 阶 | FEM Hz | 偏差 | 配对依据 |
|---|---|---:|---:|---:|---:|---|
| LS1 | 一阶正对称横弯 | 0.0365 | 1 | 0.036821 | +0.88% | family=L symmetry=S shareL=1.000 shareV=0.000 shareT=0.000 EY=1.75e+03 EZ=2.31e-13 ERX=4.38e+13 ERY=1.69 gateSENE=0.909 cableSENE=0.090 sideRatio=0.00 |
| VA1 | 一阶反对称竖弯 | 0.0700 | 2 | 0.071536 | +2.19% | family=V symmetry=A shareL=0.000 shareV=1.000 shareT=0.000 EY=3.14e-13 EZ=1.76e-08 ERX=8.41 ERY=6.19e+14 gateSENE=0.087 cableSENE=0.913 sideRatio=0.00 |
| LA1 | 一阶反对称横弯 | 0.0726 | 4 | 0.073789 | +1.64% | family=L symmetry=A shareL=0.550 shareV=0.006 shareT=0.443 EY=4.05e-09 EZ=1.31e-10 ERX=4.35e+05 ERY=1.3e+04 gateSENE=0.848 cableSENE=0.146 sideRatio=0.00 |
| TA1 | 一阶反对称扭转 | 0.0996 | 3 | 0.073357 | -26.35% | family=T symmetry=A shareL=0.509 shareV=0.007 shareT=0.484 EY=5.77e-08 EZ=1.21e-10 ERX=4.23e+05 ERY=2.62e+04 gateSENE=0.837 cableSENE=0.157 sideRatio=0.00 |
| VS1 | 一阶正对称竖弯 | 0.1028 | 5 | 0.101286 | -1.47% | family=V symmetry=S shareL=0.000 shareV=1.000 shareT=0.000 EY=1.83e-10 EZ=140 ERX=267 ERY=4.8e+14 gateSENE=0.001 cableSENE=0.999 sideRatio=0.00 |
| LS2 | 二阶正对称横弯 | 0.1087 | 7 | 0.110266 | +1.44% | family=L symmetry=S shareL=0.999 shareV=0.000 shareT=0.001 EY=197 EZ=9.29e-12 ERX=2.02e+13 ERY=11.9 gateSENE=0.314 cableSENE=0.686 sideRatio=0.00 |
| TS1 | 一阶正对称扭转 | 0.1147 | 6 | 0.103380 | -9.87% | family=T symmetry=S shareL=0.013 shareV=0.015 shareT=0.972 EY=0.349 EZ=6.13e-08 ERX=1.98e+11 ERY=2.81e+05 gateSENE=0.016 cableSENE=0.984 sideRatio=0.00 |
| SIDE1 | 边跨模态1（附件未细分） | 0.1149 | 8 | 0.116225 | +1.15% | family=SIDE symmetry=NA shareL=0.851 shareV=0.068 shareT=0.016 EY=553 EZ=2.12e-12 ERX=2.62e+13 ERY=5.46 gateSENE=0.802 cableSENE=0.198 sideRatio=1.00 |
| SIDE2 | 边跨模态2（附件未细分） | 0.1239 | 9 | 0.124857 | +0.77% | family=SIDE symmetry=NA shareL=0.404 shareV=0.352 shareT=0.027 EY=526 EZ=4.55e-11 ERX=1.84e+13 ERY=19.9 gateSENE=0.852 cableSENE=0.147 sideRatio=1.00 |
| VA2 | 二阶反对称竖弯 | 0.1438 | 12 | 0.145402 | +1.11% | family=V symmetry=A shareL=0.000 shareV=1.000 shareT=0.000 EY=1.26e-09 EZ=1.47e+03 ERX=5.95e+04 ERY=5.08e+15 gateSENE=0.000 cableSENE=1.000 sideRatio=0.00 |
| LA2 | 二阶反对称横弯 | 0.1449 | 25 | 0.220230 | +51.99% | family=L symmetry=A shareL=0.984 shareV=0.001 shareT=0.015 EY=0.000125 EZ=3.49e-14 ERX=1.69e+07 ERY=5.59e+03 gateSENE=0.981 cableSENE=0.019 sideRatio=0.00 |
| SIDE3 | 边跨模态3（附件未细分） | 0.1557 | 17 | 0.165882 | +6.54% | family=SIDE symmetry=NA shareL=0.220 shareV=0.011 shareT=0.525 EY=1.02e-08 EZ=427 ERX=2.57e+04 ERY=9.1e+13 gateSENE=0.001 cableSENE=0.999 sideRatio=1.00 |
| TS2 | 二阶正对称扭转 | 0.1571 | 16 | 0.149662 | -4.73% | family=T symmetry=S shareL=0.005 shareV=0.015 shareT=0.980 EY=4.75e-06 EZ=9.14e-08 ERX=7.4e+06 ERY=5.79e+05 gateSENE=0.733 cableSENE=0.261 sideRatio=0.00 |
| VS2 | 二阶正对称竖弯 | 0.1744 | 21 | 0.187537 | +7.53% | family=V symmetry=S shareL=0.000 shareV=1.000 shareT=0.000 EY=1.47e-09 EZ=285 ERX=649 ERY=9.82e+14 gateSENE=0.005 cableSENE=0.995 sideRatio=0.00 |

## 排除的门架 ROTX 局部模态

| 阶 | Hz | toppost SENE | cable SENE | 说明 |
|---:|---:|---:|---:|---|
| 27 | 0.223425 | 0.847 | 0.020 | LOCAL_GATE_ROTX |
| 28 | 0.225203 | 0.848 | 0.018 | LOCAL_GATE_ROTX |
| 31 | 0.231493 | 0.865 | 0.022 | LOCAL_GATE_ROTX |
| 32 | 0.231691 | 0.852 | 0.021 | LOCAL_GATE_ROTX |
| 34 | 0.240851 | 0.852 | 0.022 | LOCAL_GATE_ROTX |
| 35 | 0.248323 | 0.887 | 0.012 | LOCAL_GATE_ROTX |
| 37 | 0.251686 | 0.845 | 0.010 | LOCAL_GATE_ROTX |
| 42 | 0.258166 | 0.878 | 0.036 | LOCAL_GATE_ROTX |
| 45 | 0.265873 | 0.852 | 0.006 | LOCAL_GATE_ROTX |
| 46 | 0.267663 | 0.880 | 0.033 | LOCAL_GATE_ROTX |
| 47 | 0.273692 | 0.851 | 0.013 | LOCAL_GATE_ROTX |
| 49 | 0.287398 | 0.853 | 0.005 | LOCAL_GATE_ROTX |
