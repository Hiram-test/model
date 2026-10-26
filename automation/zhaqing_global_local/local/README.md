# 扎青吊桥索鞍：显式多钢丝实体接触与疲劳指标

`build_saddle.py` 不再使用两个方块代替主缆接触。它生成每根钢丝各自独立的圆形截面实体网格、钢丝间接触、钢丝与索鞍底板/导向板接触，并输出实际边界节点和原生 CalculiX 输入。

图纸控制数据为 283 根直径 5 mm 钢丝（03 图 TEXT 16B5）；索鞍底板 400×30×1600 mm（29 图 TEXT 20BB）；两块 110×20×1600 mm 导向板（TEXT 2097）；纵向圆弧半径为 150 CAD 单位，主视图尺寸对应毫米换算 ×10，因此采用 1500 mm（ARC 4D8B）；横向导板内净距 110 mm 根据断面线 4EC5/4ED9 的几何与标注换算。输入保留原始圆弧起止角，未把弧长强行缩成材料表的 1600 mm。图纸的平行钢丝数量和钢丝直径已核实；内部逐根排列、压紧情况、焊趾以及混凝土/锚筋约束仍需进一步闭合。

## 接触和离散

- 283 根钢丝是不同的三维实体，节点不合并；索鞍底板和两块导板另行建模。
- 候选六角密排有 786 个钢丝相邻关系，加 283 个钢丝—索鞍潜在界面。它们是**定义的潜在接触关系**，不代表全部已经闭合或发生摩擦滑移。
- 每根钢丝用一个 slave surface，master surface 合并该钢丝的低编号相邻钢丝和索鞍面；每个钢丝相邻关系仅出现一次。这避免了旧重复 slave 定义在当前原生求解器上的分配异常。
- `nc=2/4/6/12` 分别为每个截面 4/16/36/144 个四边形实体单元；圆周为 8/16/24/48 个面。截面多边形面积分别比真实圆面积少 9.968%/2.550%/1.138%/0.285%。没有暗中扩大直径补偿。
- 六角相邻方向在 `nc=6/12` 时与圆周节点对齐，初始分离支持间隙为零；`nc=2/4` 则分别有最大 0.17037/0.04278 mm 的离散间隙。接触压力仍必须进行圆周和轴向网格收敛。
- 默认 C3D8 全积分实体。输出的细模型为 464,685 个物理节点、292,096 个实体单元；所有 2,336,768 个高斯点 Jacobian 检查为正。该检查证明未发现翻转单元，不能证明疲劳应力精度。

## 荷载与初始状态

坐标为 x 纵向、y 横向、z 向上，单位 mm、N、s、MPa。左截面给定位移，右截面约束径向/横向运动并施加切向轴力，避免同一轴向自由度同时给力和位移。端面力按实际网格截面积积分分配。`boundary_interface.json` 保存真实端面节点、坐标、面积权重和切向。

默认 716150.20485 N 是用于研究的假定载荷，历史来源为水平分力控制值，**不是新整桥求解传递出的索鞍总轴力**。整桥与局部闭合时须读取最新整桥索鞍两侧真实力/运动向量。摩擦系数、弹性常数、接触罚刚度和底板固定边界都是明示的研究假设。

`--elastic-forming-stress` 给每个钢丝高斯点导入 `σ_tt = E z / R` 弹性绕鞍弯曲初应力，旋转到原生全局应力分量后，先执行零外力平衡，再加载轴力。它补上直接把钢丝设为无应力曲线所缺失的弹性弯曲部分；它不是实际制作过程的弹塑性成形历史，也不代表实测残余应力。未启用该选项时，模型明确标识无应力曲线初始状态。

## 疲劳处理

1. `extract_native_history.py` 只接受原生求解正常结束、完整循环端点和全部积分点均存在的数据；失败或仍运行的结果不会成为标签。
2. 原生 `.dat` 应力/应变顺序 `XX YY ZZ XY XZ YZ` 被显式转换为公共顺序 `XX YY ZZ XY YZ ZX`。
3. `corotate_native_history.py` 从同一时刻的全节点原生位移和实体形函数恢复各积分点 `F`，进行极分解，得到材料随转坐标中的 Cauchy 应力和 Hencky 对数应变。避免把空间 Cauchy 应力与参考 Green-Lagrange 应变直接投影到同一疲劳面。
4. `fatigue_indicators.py` 计算逐积分点应力幅、临界面法向应变幅和 SWT 指标。第一圈载荷循环不冒充稳定滞回圈。
5. 摩擦耗能只有在提供**不可逆滑移**、同一局部接触坐标中的切向力和真实接触积分面积后才积分；原生 `CDIS` 总接触位移不自动当作不可逆滑移。
6. 没有可追溯材料批次的疲劳参数和试验有效寿命范围，就不计算疲劳寿命。钢丝 1670 MPa 是图纸抗拉强度，未冒充屈服强度或疲劳参数。

## 运行

```bash
python automation/zhaqing_global_local/local/build_saddle.py results/local --nx 64 --nc 4
python automation/zhaqing_global_local/local/build_saddle.py results/local_forming --nx 16 --nc 6 --elastic-forming-stress
cd results/local_forming
OMP_NUM_THREADS=2 ccx saddle > native.log 2>&1
```

完整形成—加载—循环的 5 个步骤完成后，循环范围为累计时间 2 至 5；这些静力步的“时间”是载荷路径参数，不是已完成动力学惯性求解的物理时间。

```bash
python automation/zhaqing_global_local/local/extract_native_history.py RESULTS --start 2 --end 5 --wires 283
python automation/zhaqing_global_local/local/corotate_native_history.py RESULTS
python automation/zhaqing_global_local/local/fatigue_indicators.py RESULTS/cycle_corotated.npz RESULTS/fatigue_indicators.npz --metadata RESULTS/cycle_corotated.json
python automation/zhaqing_global_local/local/test_local_physics.py
```

上述计算脚本不绘图。模型显示/有限元云图使用原生 CGX/ParaView；数据曲线使用 Gnuplot/Origin。
