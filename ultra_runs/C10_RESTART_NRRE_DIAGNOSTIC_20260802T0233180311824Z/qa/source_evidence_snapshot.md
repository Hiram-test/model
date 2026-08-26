# 来源运行证据快照

- `source_manifest.json`：SHA-256 `52553d813ab6eb6d7ee60003a00278fa32dc0078ef1ec88014e5a9e9f13ce5b1`，记录自适应迁移运行、唯一 job 与静力诊断用途。
- `source_prepared_artifact_hashes.sha256`：SHA-256 `b7a57c28ceb286de2cdc5752c55966b38fab83b6bd55a5c1cb840566cc276e96`，包含准备期 29 个冻结输入条目。
- `source_static_status_before_finalizer.json`：SHA-256 `11f7e58b23c5db6a15d60e810d524d5fe1c77825475dd7ba3b6e231f68708c4e`，仅保留停机前状态，不代表成功终态。
- `source_operator_stop_recovery_final.json`：SHA-256 `efa6a21a4c25965feafc366fd5975833f670a5736524acaa16297ec35c385666`，证明有效十字节 `nonlinear\n` 已由 MAPDL 原生消费且进程树自然退出。
- `source_runtime_hard_stop_monitor_final.json`：SHA-256 `65c4407203f67fb4e89fc2f3c75a35284eee3a5ab5ab66fd7dc75314c0bc18c8`，证明 926 个样本、无硬事件、无监控器 terminate/kill。
- `source_solver.mntr`：SHA-256 `e365194eb9a41fbbf90597a32e93f725dd9f72ac9e0fe3da4c017a5689c16801`，证明 LS1 以 4 次迭代接受，LS2 子步 1/2 分别以 29/45 次迭代接受，累计迭代为 93。
- 所有快照均复制到本新运行的 `input_snapshot`；来源运行未被修改。
