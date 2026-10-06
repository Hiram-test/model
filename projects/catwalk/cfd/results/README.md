# 输出说明

本轮按模型保存独立结果，图表为短时试算；正常结束与统计收敛分别判断。

|目录|模型及参考表|CFD攻角|统计窗口|
|---|---|---|---|
|[`zhangjinggao`](zhangjinggao/stage_report.md)|5.6m、16索；原报告表3-1|−12、0、12°|1–2s|
|[`user_drawing`](user_drawing/stage_report.md)|新图4m净宽、8索；用户表5.8|−12、−6、0、6、12°|0.75s至实际末时刻；+6/+12°按用户要求提前停止|
|[`user_timber`](user_timber/)|新图C-C木踏板局部截面|0°|0.75–1.5s|
|[`porous_diagnostic`](porous_diagnostic/)|早期纯多孔薄面对照，已停止|−12、0、12°|仅诊断|

每组的`comparison.csv/png/pdf`对应原始参考表，`*_history.csv`保存全部原生时间记录，`selected_case_assessments.json`保存各项数值判定。新图的`loads_and_coefficients.csv`还包含每延米力、力矩及体轴系数。图上的CFD虚线仅连接已经计算的离散点。

`saved_mesh_audit.json`核对实际MSH的索数、位置、尺寸、二维挤出厚度及OpenFOAM范围；通过这些检查不等于完成网格独立性。`coefficients_stable`至少要求20个B/U的采样及分块均值稳定，本轮采样不超过2.7个B/U，不满足该条件。新图+6°在1.31696698s、+12°在1.27239497s按用户要求保存后停止，其余新图算例至1.5s。

`scripts/assess_results.py`另可生成全工作目录的`status.json`与`coefficients.csv`，其中会包含旧比例和失败版本，适合历史索引。本轮结果以表中子目录为入口。

原生网格、初始/末时刻场、字典、forceCoeffs、日志及每例运行清单随Release结果包保存。三维CAD和历史试算另有清楚标识；本阶段没有三维流场结果。
