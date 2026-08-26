# A30 全部非圆截面轴基线结果

- 状态：`COMPLETED_BY_INPUT_IDENTITY_WITH_A10_RESULTS`
- QA：`PASS_RESULT_REUSE_WITH_DOCUMENTED_LIMITATIONS`
- H175：A10 已修正 2,698 根并完成全桥求解。
- RHS50×30：A20 已证明 2,898/2,898 根在 B00 中本来正确，物理改动数为 0。
- A30 候选 11 项依赖与 A10 字节身份：一致。
- 静力：LS1/LS2 均收敛；端点 STEN/SENE=2.667479851077623e-34/2.667479843364189e-34；质量误差=1.061380316969007e-09 tonne；反力相对误差=1.907675526569801e-11。
- 日志：四份 OUT 与四份 ERR 为 0 ERROR、0 FATAL、0 negative pivot、0 zero pivot；五条已知 warning 全部逐项处置。
- LINK180：73692 个唯一元素全部覆盖，非正轴力 0，最小轴力 519006.875 N。
- 模态：80/80/80、80+80 节点向量、80 行主能量及 80×6 六组件能量完整；第 59 阶越过 0.35 Hz，频带未被阶数截断。
- 源完整性：平衡 DB、静力 RST、模态 DB、RSTP 的当前 SHA-256 与两套只读 POSTONLY 前后身份一致；A30 QA 未改源文件。
- 父运行元数据：A10 共 320 个文件、A20 共 9 个文件的路径、大小与 mtime_ns 在本次 QA 前后完全一致。
- 关键结果：8 类关键二进制当前哈希均与 A10 finalizer 全 run 账本一致，160 份向量全部受账本覆盖。
- 新 A30 MAPDL 作业：未启动；原因是输入完全相同，重复求解没有新增物理信息。
- 未决：全历程逐子步 STEN/SENE 未保存；十四目标物理 mapping 与报告 MAC 尚未封板，详见 `qa/unresolved_source_items.md`。
- 下一实际物理变体：`S10_SECTION_SHEAR`。
