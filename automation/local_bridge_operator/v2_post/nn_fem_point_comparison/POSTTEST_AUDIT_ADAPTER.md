这是一项测试开放之后的审计元数据适配，不能称为测试前冻结。原 render_native_nn_point_comparison.py、point_plot_plan.json、pretest_source_freeze.json 以及原 README 全部保留原字节。

唯一兼容事项是 selected-native auditor 的导出文件键映射：rebar 回调的 npz/metadata 是逻辑键，应映射到同一 case 的 row 显式原路径；friction 仍按原文件 basename。旧 FileNotFoundError、旧 auditor 源、新 auditor 源、确切 diff、修订验证及独立复核均以 SHA 绑定。该修订不改变原 native 期望 SHA，不改求解结果、模型、预测、资格门或误差阈值。

新执行源为 render_native_nn_point_comparison_posttest_audit_adapter.py。只有 guard 函数 AST 改变，其余 14 个函数以及模块入口 AST 与原预冻版本一致。四个注册案例、active 固定模型、末帧、全部真实位移节点/应力积分点、向量差和张量差范数、应力非对角 2 权重、同家族共享色标与相机均不变。每张图未来的回执会额外绑定本 posttest addendum 与旧失败/修订/独立复核。

本目录的 posttest_audit_adapter_static_checks.json 和 posttest_audit_adapter_static_review.json 只证明静态接口；当前没有读取测试场数组、导入数值/绘图库或生成图，实际峰值内存和视觉验收未完成。即使静态通过，也仍需两项最终审计完成与 owner 资源窗口授权，再沿用原 README 命令参数，仅将 Python 文件名改为这个 posttest 版本。输出目录必须是本目录下此前不存在的新子目录。

不改五图主报告，不改正式数值文件。后续 ZIP 每个成员真实 CRC 和 SHA 验证后，独立回执可使用 PASS_COMPLETE_ZIP_VERIFICATION 与 archive={path,bytes,sha256}；这一打包状态不是科学准确性 PASS。
