# V2 中文 HTML 与 JSON 报告生成器

当前交付是生成器及静态／合成语义验证，不是最终科学报告。没有读取新 test/OOD 参数或响应，没有运行求解器或优化器。最终运行应由 root 在正式训练、模型封存、独立 release、完整场测试及独立审计完成后明确触发。

```bash
python /dev/shm/bridge_complex_v2_20261025/report/verify_report_generator.py
python /dev/shm/bridge_complex_v2_20261025/report/v2_report.py \
  --inputs /dev/shm/bridge_complex_v2_20261025/report/report_inputs.json \
  --output-directory /dev/shm/bridge_complex_v2_20261025/report/final \
  --final
```

生成器先核固定 `audit/v2_test_release_verification.json` 与 `v2_test_release.json`，再核独立20阶段／8轮补算审计、模型实际 SHA、控制器执行锁、独立完整场审计，以及全部选中原生参考的原始字节／实体身份审计。它永远拒绝读取封存输入描述文件；放行前拒绝读取 V1/V2 最终测试目录。证据缺失或不一致时退出码为2，仅写 `report_generation_blocked.json`，不写最终 HTML 或完成摘要。

输出：

- `V2非线性神经算子实验报告.html`：自包含中文报告，嵌入真实统计图与已核验的5张原生结果／尺寸图。
- `v2_result_summary.json`：逐家族、策略、test/OOD、物理组、逐工况的精炼摘要，完整源路径/SHA清单。
- `charts/`：Matplotlib 统计图及逐图 JSON 收据；包含完整场组误差、冷算预算／新增算时／真实历史计数，以及按ID字典序选取的test/OOD逐原始帧位移、应力误差。没有构造NN空间应力云图。
- `report_receipt.json`：报告、摘要与生成器的实际 SHA 和字节数。

报告将真实独立工况与分组、历史访问、帧损失、优化更新分开。原生失败保留注册分母，但不计作NN–FEM误差负样本。模型比较仅使用同一批新参考；历史V1仅在单独独立完整场与配对审计PASS后显示，原发射为V1 active单seed17的absolute_normalized_state，明确不属于等算力且仅改loss的消融。

热—力读取其最终资格收据，允许真实HOLD；未提供则显示缺失，不从coarse解、dataset接口或规划推导“已训练”。5张原生图的绘图PASS仅表示字段与图像核验，研究试件尺寸图不是扎青吊桥施工图。材料端点闭合与完整原生J2增量路径、固定离散与连续体参考资格、正式结果与开发应力缩小／梯度对照分别报告。

`runtime_observation.json` 是生成器准备时对共享环境的实际观察，包含Python、torch、numpy、scipy、matplotlib及原生wrapper/ELF完整SHA；不冒充每个历史进程的启动收据。项目是固定绝对路径科研运行快照，GitHub源码之外仍依赖旧V1数据、模型、原生求解器和已保存证据，不能声称clone后无依赖运行。

静态验证使用明确标注的合成逻辑／解析张量，检查原生失败分母、已知初始帧与边界掩码、张量剪切权重、零参考归一化floor、释放前读取防护和缺失证据阻断；这些验证不计作FEM工况或正式科学测试。所有新Python非空行均通过真实COMMENT token检查。
