# 三维 T 梁：VLM 微型 PSO、AMBER 与局部预测型 AFEM 比较代码

本包只交付比较代码和接口，不声称已经完成三方法数值对比，也不包含伪造的 AMBER 权重或局部变分求解结果。

## 方法

- `vlm_trace_micro_pso`：读取 `comparison/vlm_trace.json`。该文件记录了对固定粗解图 `comparison/assets/coarse_state_montage.png` 的公开视觉观察、图像 SHA256、六区域优先级、五维动作中心和资源转移方向。执行器只搜索“整体尺度”和“热点对比”两个坐标，使用五个初始粒子，并只更新四个非最优粒子一次；最多九次低成本代理评价，内部完整 FEM 为零次。
- `amber_iterative_sizing_field`：当前网格图与节点特征送入外部 AMBER 检查点，得到逐节点标量尺寸场，经确定性网格器形成下一张中间网格并迭代。未提供检查点时明确返回 `external_component_required`。
- `local_prediction_h_afem`：对六个 T 梁物理区域建立局部 h 细化候选，由外部低维局部富集或替换问题返回“预测的全局有效误差下降”，再按真实新增 DOF 和 Dörfler 比例标记。每轮只在组合动作越过终局预算上限时做最小整体回缩，不会第一轮就强行吃满全部预算。未提供局部预测器时明确返回 `external_component_required`，不会用 ZZ 排名冒充该方法。

## 公平比较协议

三种方法共享同一个三维实体 T 梁、粗网格、粗解、恢复应力、ZZ 场、终局 DOF 预算、C3D4 网格编译器和终局完整 FEM 评价。成本记录区分离线标签与训练、代理评价、网格编译、局部预测、方法内部完整求解和终局完整求解。

## 默认命令

```bash
python tbeam_compare_code_only.py --output-dir comparison_plan
```

默认只写 `benchmark_plan.json`，不运行有限元比较。

只运行已实现的 VLM 微型 PSO 链路：

```bash
python tbeam_compare_code_only.py --execute --methods vlm --output-dir comparison_run
```

接入真实 AMBER 检查点和局部预测器后的统一入口：

```bash
python tbeam_compare_code_only.py --execute --methods vlm amber local \
  --amber-command "python external_templates/amber_infer_stub.py --request {request} --response {response}" \
  --local-command "python external_templates/local_patch_predict_stub.py --request {request} --response {response}" \
  --output-dir comparison_run
```

模板会故意抛出 `NotImplementedError`，直到替换为真实外部实现。

## 静态验收

```bash
python -m compileall -q tbeam_fem_core.py tbeam_compare_code_only.py comparison external_templates
pytest -q comparison/tests/test_code_contracts.py
```

测试覆盖图像哈希绑定、三方法计划、局部动作映射、微型 PSO 最大评价预算，以及所有新增 Python 源码“每条非空代码行均有注释”。
