# 已闭合轻量源批次

此清单以 GitHub `Hiram-test/model` 分支 `codex/complex-fullfield-v2-20261025` 的只读观察 `c4312088d82accce4f5515a5d4220575e63b5602` 为基准。父代理发布前须再次读取远端 head，并将本批增量合入最新树；不能把旧 tree 整体覆盖其他并发成果。本工具只复制工作区文件、核对哈希和生成清单，没有调用任何 GitHub 写入接口。

- `v2_report/`：热最终独立资格、独立 decoder 开发负结果、最终 checkpoint 实际训练支持接口已接入；旧报告源码与收据保存在 `history/before_thermal_probe_support_v2/`。正式最终报告尚未运行。
- `v2_constitutive_decoder_probe/`：保留真实 `NOT_PROMOTED` 结果。旧 8/3 开发数据、2 epoch 的 96 个 optimizer update 不并入正式 6 个模型或其工作量。`.pt`、`.npz`、完整事件流和日志已由单独归档及保存收据覆盖，本轻量批次不重复装入 Git。
- 原审计器既有路径：新增已闭合检查器并更新最终字段/历史基线异常 schema 的验证代码；`v2_history/` 保留旧版本。坐标修正的历史收据继续精确指向当时 9d79 版本，新修正收据串联 9d79 → 27764 与 455c → 466d，不更改旧收据的预期 SHA。
- `v2_evidence/audit_closed_interface/`：独立白名单、修正理由、11 项显式合成异常接口检验和报告静态交接结果。未包含封存参数、未来 release 或运行中的科学结果 JSON。
- `v2_delivery/closed_packaging/`：未来 rebar 训练、新测试及完整预测证据的有界分包接口，仅做合成字节验证，尚未打包活动训练；原 V1 数据/依赖仍通过已保存归档索引复用。

每条 manifest 记录运行源绝对路径、仓库相对路径、本地副本、SHA256、Git blob SHA1、字节数与相对观察远端的 ADD/UPDATE/UNCHANGED。源码经 AST 与每个非空行真实 COMMENT token 检查，复制前后核源 stat/SHA，复制后再核目标字节。二进制数值数据未导入，Torch 和原生求解均未执行。

发布不会令固定绝对路径科研快照变成零依赖产品。原生求解器、旧 V1 数据与训练权重需要按实际归档/重现索引取得；报告如实保留 full-entity、固定离散和 reference HOLD 边界。图像完整性 PASS、材料约束自检 PASS、最终统计审计 PASS 与工程精度或网格资格是不同结论。
