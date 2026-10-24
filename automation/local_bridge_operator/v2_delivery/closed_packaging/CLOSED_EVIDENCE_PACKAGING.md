# 有界证据分包接口

此接口只为完成后的 rebar 训练与正式新测试准备。当前没有创建这些大证据包，没有读取封存测试参数或新测试响应，没有启动 Torch、训练或原生求解。

`v2_closed_evidence_packager.py` 沿用已验证检查点的流式 SHA256、双次 stat/SHA、ZIP 完整解压与 CRC 方法。每次只产一份 ZIP；默认每份原始数据不超过 250,000,000 字节，单个大文件以 128,000,000 字节的精确连续范围拆分，压缩后严格小于 350,000,000 字节。缓冲为 1 MiB，写入前测量可用空间并保留 50 MB。分块只用于无损传输，不改变任何模型、网格、字段或时间步。

## 完成后允许的清单

| 配置 | 必需闭合证据 | 纳入范围 | 排除范围 |
|---|---|---|---|
| `rebar-training` | `training_complete.json` 的真实完成状态与未生成新测试标志；确切 10 个 strategy/round/seed stage_commit；每份已提交文件 SHA；账本无 STARTED；4 轮获取完成 | rebar 全部 10 个训练 stage、训练日志与实际事件、round/budget、收据绑定的新 native 成功与失败 attempt、被接受标签完整字段 | 新测试输出、旧 train 缓存、其他活动分支、封存输入 |
| `new-tests` | 固定 release verification、20-stage completion audit、V2 field audit、selected native identity audit、selected weight support audit、V1 baseline field audit 均完成；共享 released-index SHA | 两 family 的 V2 三策略、独立 V1 基线完整预测/参考/差值与每 case 收据；16 个注册原生 reference/失败证据目录；审计与冻结模型元数据 | 封存输入、外部旧训练数据、未完成分支 |

失败 reference 仍占注册槽位。若 released index 没有明确的失败证据目录，规划会报错并要求 producer 提供真实位置，不能删除失败槽位来做出成功包。这里的审计 PASS 指证据完整性；它不会将精度、物理或网格 HOLD 改写成科学通过。

计划文件逐原始文件记录相对路径、完整 SHA256、长度和 stat，并保存原始文件到 ZIP member/offset 的重建映射。每份 ZIP 收据记录每个 member（包括生成元数据）的 SHA256、CRC、完整解压核验和压缩前后源身份。最终 `verify-reassembly` 会从所有 ZIP 中逐字节读取、按 offset 重组摘要，核对每个完整原文件的长度和 SHA256，且不产生大型解压副本。

## 未来执行命令

仅在 root 确认对应真实完成标记后执行。不要用一个 while 自动打包全部份；逐份交付并安排空间后再运行下一份。以下目录均为运行快照的固定绝对路径，不代表 clone 后无需外部数据即可运行。

```bash
python /dev/shm/bridge_complex_v2_20261025/delivery/closed_packaging/v2_closed_evidence_packager.py plan --profile rebar-training --output /dev/shm/bridge_complex_v2_20261025/checkpoints/rebar_closed_parts_plan.json
python /dev/shm/bridge_complex_v2_20261025/delivery/closed_packaging/v2_closed_evidence_packager.py pack --plan /dev/shm/bridge_complex_v2_20261025/checkpoints/rebar_closed_parts_plan.json --part 1 --output-directory /dev/shm/bridge_complex_v2_20261025/checkpoints/rebar_closed_parts
python /dev/shm/bridge_complex_v2_20261025/delivery/closed_packaging/v2_closed_evidence_packager.py plan --profile new-tests --output /dev/shm/bridge_complex_v2_20261025/checkpoints/final_new_test_parts_plan.json
python /dev/shm/bridge_complex_v2_20261025/delivery/closed_packaging/v2_closed_evidence_packager.py pack --plan /dev/shm/bridge_complex_v2_20261025/checkpoints/final_new_test_parts_plan.json --part 1 --output-directory /dev/shm/bridge_complex_v2_20261025/checkpoints/final_new_test_parts
```

全部份可访问后进行最终无副本重建验证，例如：

```bash
python /dev/shm/bridge_complex_v2_20261025/delivery/closed_packaging/v2_closed_evidence_packager.py verify-reassembly --plan /dev/shm/bridge_complex_v2_20261025/checkpoints/rebar_closed_parts_plan.json --archive-directory /dev/shm/bridge_complex_v2_20261025/checkpoints/rebar_closed_parts --output /dev/shm/bridge_complex_v2_20261025/checkpoints/rebar_reassembly_receipt.json
```

合成接口验证 `verify_closed_packager.py` 只使用少量人工字节文件；结果 `packager_verification.json` 不属于 FEM、模型或正式测试证据。脚本不会上传、删除已有证据或自动清理任何归档。
