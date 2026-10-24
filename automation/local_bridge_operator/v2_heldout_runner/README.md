# V2 新测试工况原生求解编排器

这份目录保存独立编排器、合成验证、历史源码和独立静态审查。它不包含封存的测试参数、放行凭据、真实测试响应或模型权重。源码已通过 20 项合成检查；独立审查为只读静态审查，没有独立重跑这些合成测试，也没有启动真实求解。实际训练、放行和测试完成状态应以各自正式凭据为准，不能由本目录推断。

## 文件与身份

- `v2_evaluation_native_runner.py`：当前编排器，SHA-256 `7fc184b60eeed66297595cc7dbb696d6c39f3057ab31a4aec9365b86659ba9df`。
- `v2_evaluation_native_runner_verify.py`：纯标准库合成测试，SHA-256 `5738ebccdbe94b9b56cf2e642d744ecbfd4787ed50791d0e93445e73bcfa0f3c`。
- `evaluation_native_runner_verification/verification.json`：20 项生产者合成验证报告，SHA-256 `e1f7776ab39ebc1fcd842a2bcc635c3abc31358866564e552297dfaf2e837886`。
- `audit/v2_evaluation_native_runner_static_review.json`：独立静态审查，SHA-256 `2a04868dee481a85c7a76a94dd75b19ef2f10c3901dfaa0587377efca15742b1`。
- `evaluation_native_runner_verification/source_history/`：三份真实历史源码，保留修复前的版本。它们有已知恢复边界问题，不能代替当前编排器执行正式测试。
- `publication_manifest.json`：逐文件原始路径、仓库目标路径、SHA-256、Git SHA-1 blob、字节数和复制状态。清单自身的身份另列在发布回执中，避免自引用哈希。

每个 Python 非空行均保留真实注释。仓库中的副本与对应运行源逐字节一致，没有为了改变目录而改写冻结代码。原 V2 训练、选样、物理回调和模型源码均不在本次变更范围内。

## 行为与失败分母

固定顺序为摩擦家族八条、钢筋家族八条；每家族四条测试、四条 OOD。两家族全部十六个注册槽始终可见。编排器同步调用一个回调，并用持久文件锁阻止两个编排进程重叠执行。摩擦调用冻结的 `solve_evaluation(desc, release)`，钢筋调用冻结的 `solve_candidate(desc, heldout_release=release)`；原适配器仍会复核授权和原生证据。

逻辑 `id/group_id/split` 不因原生完整性重放改变。`actual_native_case_id` 和 `native_replay_used` 单列实际来源；原 NPZ、metadata、原生 receipt 和成本链保持不变。实际原生失败以原槽的关闭失败状态保留，不换成其他历史，也不当作可信 FEM 对神经网络的误差负样本。

已经完整提交的槽在重启时只核验凭据，不再调用适配器。已保存完整 `callback_result.json`、但编排完成凭据未保存时，可核验原回调保存的预期导出哈希后关闭该槽。不能重新计算当前文件哈希来接受变化的导出。缺失原执行意图、但遗留回调结果或异常证据时，立即拒绝重新求解。

只有 `STARTED` 或不明异常、没有完整回调结果时，槽保持 `PENDING_FEM` 并停止。审计可用独立 reconciliation 凭据，绑定原意图、实际终止证据和完整原生成本，读取既有结果或明确关闭失败；这条路径不重跑求解器。未知成本不写成零，回调墙钟不替代原生求解耗时。只要有待处理槽，最终模型评估不得启动。

## 放行与正式命令

编排器不直接读取封存输入文件。独立审计须先确认完整训练与选样闭环，签发强放行凭据，并发布可读 descriptor envelope 和单独的源码附录。附录绑定首次 release、verification、公开 envelope、编排器、既有适配器及运行配置的精确身份。编排器先核这些身份，再读取 envelope；逐条调用原强 guard 核验完整物理工况承诺。

运行路径固定在 `/dev/shm/bridge_complex_v2_20261025`。仓库副本用于持久保存与复核；正式重现需要依据发布清单恢复到原运行路径，并恢复既有 V2 原生适配器、审计 guard、模型和数据依赖。不能修改代码中的路径后继续声称原冻结 SHA 有效。

在原 `operator` 目录执行：

```bash
python v2_evaluation_native_runner.py \
  --config v2_controller_config.json \
  --release ../audit/v2_test_release.json \
  --released-descriptors ../audit/v2_released_evaluation_descriptors.json \
  --source-addendum ../audit/v2_evaluation_native_runner_freeze.json
```

如独立审计已经出具明确恢复凭据，才增加：

```text
--reconciliation ../audit/v2_evaluation_native_reconciliation.json
```

固定输出为 `operator/evaluation_native/released_index.json`。`families.friction` 与 `families.rebar` 各八条。顶层状态只有在全部槽关闭后成为 `NATIVE_EVALUATION_COMPLETE`，并生成含十六个完成凭据引用的 `completion.json`。`qualified_reference_histories`、`closed_reference_failures`、`pending_histories` 分别计数。完成编排不等于全部原生参考合格，更不等于神经模型误差或物理检查通过。

## 合成验证范围

可在具备写入空间的独立副本目录运行：

```bash
python v2_evaluation_native_runner_verify.py
```

测试使用明确标注的人工文件、人工成本和 stub 回调；不导入 Torch、不调用 FEM、不读取真实封存参数或新测试响应。覆盖正常与失败槽、实际重放名称、完成后零回调恢复、导出字节变化、孤立事务、异常部分成本、审计明确关闭、已保存回调后的中断恢复、全局排他锁和授权前拒绝读取。合成字节和成本不能用于任何科学精度或效率结论。

## 本次发布边界

只发布代码、文档与已经闭合的 JSON 检查证据。明确排除合成二进制、临时测试目录、真实 NPZ/DAT/FRD、封存参数、放行文件、未来公开 descriptor envelope 和运行中的工况账本。本次仅准备仓库内容及清单，不提交或推送分支；最终 GitHub 发布由主任务统一完成。
