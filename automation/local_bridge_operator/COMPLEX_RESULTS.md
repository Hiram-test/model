# 复杂非线性全场算子与误差驱动补算

新分支取消固定 POD、模态截断、预测图粗化及多项式响应基线；保留有限元节点、体积分点和已导出的界面状态。负样本定义为同工况的原始神经预测与合格有限元参考场之间的超阈值误差。

|物理分支|参考历史去重数|初始测试平均误差|主动补算后|随机补算后|主动模型测试通过|
|---|---:|---:|---:|---:|---:|
|摩擦接触|27|42.311%|37.915%|38.938%|0/4|
|钢筋塑性与界面滑移|26|69.206%|55.418%|52.145%|0/4|
|热传导与弹塑性|参考解 HOLD|未训练|未训练|未训练|未放行|

摩擦接触：离散有限元场复现；工程适用性另行判断 HOLD: actual mesh sensitivity exceeds the registered5percentthreshold for some contact and volume-stresspeaks
主表为普通测试均值；域外测试均值（初始／主动／随机）为 62.115%／48.137%／49.854%。普通＋域外测试的误差负样本：initial 8/8；active 8/8；random 8/8。

钢筋塑性与界面滑移：Fixed discretization reproduction training only; continuum local stress convergence within ten percent is not established. HOLD_20.995_PERCENT_COMMON_POINT_DIAGNOSTIC
主表为普通测试均值；域外测试均值（初始／主动／随机）为 78.301%／73.085%／70.087%。普通＋域外测试的误差负样本：initial 8/8；active 8/8；random 8/8。

热传导与弹塑性：参考资格未通过，正式训练与神经测试未执行；The final bounded reference qualification did not pass the unchanged full-field spatial/temporal gates; no19history production set, neural training, or active FEM acquisition is released for this family.

数值求解完成、代理误差通过、完整非线性物理平衡通过及工程适用性分别记录。所有原始失败、被隔离的输出、修复和反例保留。

完整逐工况误差、原生检查和数据身份见结果包中的 `build/complex-nonlinear-20261024/delivery_summary.json`。
