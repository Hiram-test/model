首次真实运行已完成四个预先固定案例的完整数组身份检查与点值图输出，峰值 RSS 为 116,039,680 B（110.66 MiB）。所有原生参考物理检查通过，四个 NN 物理状态仍为 HOLD；没有按误差重新选择案例。

首次图面验收未通过：右侧色条刻度越出画布，顶行标题与说明位置靠近，自动色条与三维坐标轴标签冲突。原 rendered/ 下的 PNG、点值 NPZ、receipts、render_index 原样保存；失败记录见 initial_render_visual_qa.json。

新 render_native_nn_point_comparison_postrender_layout_v2.py 仅更改两个布局调用：六个三维面板用明确画布矩形，六根色条用独立画布矩形。逆向还原这两个调用后，整个 render 函数 AST 与冻结的 posttest_audit_adapter 版本相同。新 wrapper 不再读取完整 NN/FEM 历史，只读取已核验的原 point_values.npz；对其中每一个数组重新核对 dtype、shape 与完整数值字节 SHA。四个案例、active 模型、真实末帧、全部节点/IP、向量和张量差、单位、掩码、相机、共享色标和原始误差/HOLD 文本均不变。

此修订清楚标为 post-render layout-only，绝非测试前冻结。只有独立静态复核完成并写出 postrender_layout_v2_source_freeze.json 后才执行；修后图仍需逐张视觉检查。所有最终 visual PASS 均只是图面合格，不能解除 NN 科学准确性或物理门 HOLD，也不解除参考连续体网格精度 HOLD。
