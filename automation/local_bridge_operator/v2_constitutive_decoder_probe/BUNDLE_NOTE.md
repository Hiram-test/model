# 独立本构应力解码器开发证据包

本包记录一次已结束的独立开发实验：原生代数回代与梯度验证通过，两轮神经网络训练的实际误差未达标，结论为 **NOT_PROMOTED**。不属于正式 V2 的六个模型，也不是新测试集结果。

主要入口是 `constitutive_decoder_probe/PROBE_RESULT.md`、`result_summary.json` 和 `final_result_manifest.json`。真实训练事件、检查点、训练日志、逐组误差、应力幅值与独立审计保存在 `training/`。

原七个冻结文件与此前 GitHub 提交 `3699854be363c8bcb41b4440038f21d67b0801d5` 一致。原始数据与完整基础 V2 项目不在本包中；本次物理与本构模块快照已包含，其余依赖的身份、SHA256 与运行时路径在 `frozen_probe_plan.json`、`publication_manifest.json`、`training/probe_contract.json` 中。运行时绝对路径是来源标识；此包是含选中权重的证据包，不能在缺失原始项目依赖和数据时直接重新训练。

`publication_manifest.json` 保留了训练开始前的历史状态，其中的 pending 与 do_not_copy 提示当时有效。现在以新增 `final_result_manifest.json` 和 `probe_status.json` 为最终状态；原冻结七文件的内容未修改。

ZIP 条目与 SHA256 清单应全部核验后再使用。`training/checkpoint_tensor_audit.json` 是不加载 Torch 的张量存储与元数据审计；同进程新对象的实际预测回放差为零，二者都没有被称为独立进程的完整实验复现。
