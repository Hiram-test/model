# E20 与附件2-3表4-1物理模态配对

配对依据振型物理特征（有效质量方向、两幅猫道同/反相、主跨正/反对称、SENE 组件占比），
禁止仅按频率阶次硬配。门架上端释放 ROTX 产生的平面内局部模态单独列出，不进入表4-1。

| 表4-1 | 说明 | 实测 Hz | FEM 阶 | FEM Hz | 偏差 | 配对依据 |
|---|---|---:|---:|---:|---:|---|
| LS1 | 一阶正对称横弯 | 0.0365 | 1 | 0.036826 | +0.89% | family=L symmetry=S shareL=1.000 shareV=0.000 shareT=0.000 EY=1.75e+03 EZ=7.22e-10 ERX=4.38e+13 ERY=1.77e+03 gateSENE=0.355 cableSENE=0.582 sideRatio=0.00 |
| VA1 | 一阶反对称竖弯 | 0.0700 | 2 | 0.071525 | +2.18% | family=V symmetry=A shareL=0.000 shareV=1.000 shareT=0.000 EY=4.57e-12 EZ=5.49e-06 ERX=56 ERY=6.19e+14 gateSENE=0.075 cableSENE=0.883 sideRatio=0.00 |
| LA1 | 一阶反对称横弯 | 0.0726 | 3 | 0.073604 | +1.38% | family=L symmetry=A shareL=1.000 shareV=0.000 shareT=0.000 EY=6.08e-08 EZ=1.28e-10 ERX=5.05e+05 ERY=5.72e+06 gateSENE=0.573 cableSENE=0.265 sideRatio=0.00 |
| TA1 | 一阶反对称扭转 | 0.0996 | 4 | 0.084445 | -15.22% | family=T symmetry=A shareL=0.004 shareV=0.015 shareT=0.981 EY=1.05e-07 EZ=4.2e-08 ERX=452 ERY=4.91e+04 gateSENE=0.533 cableSENE=0.130 sideRatio=0.00 |
| VS1 | 一阶正对称竖弯 | 0.1028 | 5 | 0.101271 | -1.49% | family=V symmetry=S shareL=0.000 shareV=1.000 shareT=0.000 EY=4.08e-07 EZ=140 ERX=6.34e+04 ERY=4.8e+14 gateSENE=0.001 cableSENE=0.998 sideRatio=0.00 |
| LS2 | 二阶正对称横弯 | 0.1087 | 7 | 0.110284 | +1.46% | family=L symmetry=S shareL=0.997 shareV=0.000 shareT=0.003 EY=197 EZ=1.11e-07 ERX=2.01e+13 ERY=4.02e+05 gateSENE=0.249 cableSENE=0.679 sideRatio=0.00 |
| TS1 | 一阶正对称扭转 | 0.1147 | 6 | 0.106073 | -7.52% | family=T symmetry=S shareL=0.017 shareV=0.015 shareT=0.968 EY=0.688 EZ=3.75e-07 ERX=2.75e+11 ERY=6.46e+05 gateSENE=0.153 cableSENE=0.744 sideRatio=0.00 |
| SIDE1 | 边跨模态1（附件未细分） | 0.1149 | 8 | 0.116224 | +1.15% | family=SIDE symmetry=NA shareL=0.340 shareV=0.229 shareT=0.083 EY=553 EZ=8.07e-15 ERX=2.62e+13 ERY=10.2 gateSENE=0.805 cableSENE=0.178 sideRatio=1.00 |
| SIDE2 | 边跨模态2（附件未细分） | 0.1239 | 9 | 0.124855 | +0.77% | family=SIDE symmetry=NA shareL=0.240 shareV=0.215 shareT=0.131 EY=526 EZ=4.96e-12 ERX=1.84e+13 ERY=0.859 gateSENE=0.846 cableSENE=0.140 sideRatio=1.00 |
| VA2 | 二阶反对称竖弯 | 0.1438 | 12 | 0.145407 | +1.12% | family=V symmetry=A shareL=0.000 shareV=1.000 shareT=0.000 EY=2.45e-09 EZ=1.47e+03 ERX=3.96e+04 ERY=5.07e+15 gateSENE=0.000 cableSENE=1.000 sideRatio=0.00 |
| LA2 | 二阶反对称横弯 | 0.1449 | 26 | 0.220273 | +52.02% | family=L symmetry=A shareL=0.988 shareV=0.001 shareT=0.011 EY=0.00012 EZ=7.56e-08 ERX=1.59e+07 ERY=4.96e+07 gateSENE=0.870 cableSENE=0.082 sideRatio=0.00 |
| SIDE3 | 边跨模态3（附件未细分） | 0.1557 | 17 | 0.165881 | +6.54% | family=SIDE symmetry=NA shareL=0.070 shareV=0.198 shareT=0.242 EY=1.34e-09 EZ=427 ERX=3.33e+03 ERY=9.1e+13 gateSENE=0.001 cableSENE=0.999 sideRatio=1.00 |
| TS2 | 二阶正对称扭转 | 0.1571 | 16 | 0.151000 | -3.88% | family=T symmetry=S shareL=0.004 shareV=0.020 shareT=0.976 EY=2.88e-06 EZ=9.98e-07 ERX=1.83e+06 ERY=7.95e+06 gateSENE=0.549 cableSENE=0.079 sideRatio=0.00 |
| VS2 | 二阶正对称竖弯 | 0.1744 | 21 | 0.187522 | +7.52% | family=V symmetry=S shareL=0.000 shareV=1.000 shareT=0.000 EY=4.45e-07 EZ=286 ERX=7.14e+04 ERY=9.84e+14 gateSENE=0.005 cableSENE=0.994 sideRatio=0.00 |

## 排除的门架 ROTX 局部模态

| 阶 | Hz | toppost SENE | cable SENE | 说明 |
|---:|---:|---:|---:|---|
| 28 | 0.221916 | 0.801 | 0.017 | LOCAL_GATE_ROTX |
| 30 | 0.228899 | 0.805 | 0.020 | LOCAL_GATE_ROTX |
| 32 | 0.231520 | 0.756 | 0.027 | LOCAL_GATE_ROTX |
| 34 | 0.238197 | 0.807 | 0.020 | LOCAL_GATE_ROTX |
| 36 | 0.248332 | 0.826 | 0.016 | LOCAL_GATE_ROTX |
| 41 | 0.254524 | 0.825 | 0.036 | LOCAL_GATE_ROTX |
| 44 | 0.262676 | 0.802 | 0.006 | LOCAL_GATE_ROTX |
| 46 | 0.264108 | 0.828 | 0.033 | LOCAL_GATE_ROTX |
| 47 | 0.270944 | 0.802 | 0.015 | LOCAL_GATE_ROTX |
| 49 | 0.284451 | 0.802 | 0.005 | LOCAL_GATE_ROTX |
