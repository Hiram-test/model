# I08 CCX 43 工况交付清单

交付日期：2026-08-30（UTC）

## 最终文档

- 文件：`超长猫道智能预警系统_第二章抖振知识图谱与智能体推演_20260830_FINAL_R1.pdf`
- 页数：30 页 A4
- SHA-256：`2d17882bfce050f66d68579ea42cbbf3354f69e005ce7c4e591d055f54d86c28`
- 口径：43/43 数值证据完整性与计算链 QA PASS；不等于结构安全验收、施工放行或预警策略签署。

## 结果摘要

- 文件：`I08_CCX43_FINAL_SUMMARY.md`
- SHA-256：`565821ec8f5fdf1b077fb49aa420fa7c11cd1f3e9b6a7f5272fb47e73529d707`

## 证据包目录

- `I08_RUN_ROOT/`：GitHub 工作流权威输入、43 案矩阵、执行门、作业/结果清单、原子稳定性审计、管线与 QA 程序、根级 SHA 账本及两份运行错误日志。
- `I08_POSTPROCESS/`：43 案 acceptance、主表、站点结果、索力结果、协方差、知识图谱 JSON-LD、三元组、分类汇总、warning-policy 合同、493 项 SHA 账本与后处理自检。
- `agentic_kg/`：知识图谱构建器、合同/说明、JSON、GraphML、三元组、43×4 智能体轨迹、状态、自检、KG SHA 账本与独立错误日志。
- `PDF_CHAPTER2_WORK/`：第二章 TeX、数据注入器、图表生成器、最终图表、图表审计、编译/渲染/字体/文本复核记录及 PDF 错误日志。
- `I06_CHAPTER2_CONTENT/`、`I06_CHAPTER2_FIGURES/`：第二章前置 CCX 证据蓝图与图表支撑。
- `FINAL_DOCUMENT/`：最终 R1 PDF。
- `SUMMARY/`：最终结果摘要与本清单。

## 冻结结论

- GitHub 精确工况：43 案；`stationary_ok=35`，`reference_only=8`。
- CCX：43/43 作业返回 0；独立逐案 QA 43/43 PASS；493/493 SHA 校验通过。
- 知识图谱：2520 节点、2953 边；43 案各 4 步，共 172 个 AgentDecision。
- 智能体终态：`STOP_AND_NONLINEAR_REVIEW=12`、`REFERENCE_ONLY_NONSTATIONARY=4`、`NUMERICAL_EVIDENCE_READY_HUMAN_REVIEW=27`、`WAITING_FOR_SOLVER_EVIDENCE=0`。
- 运行策略：43/43 `NOT_ARMED`，43/43 `dispatch=false`。

## 体积边界与原始载荷

证据 ZIP 不重复纳入数 GB 的逐步 `.dat`、`.inp`、`.sta`、`.cvg`、`.frd` 原始求解负载，以避免交付件不必要膨胀。其完整身份、路径、输入/输出哈希、返回码、案例顺序与发布后稳定性由以下冻结证据覆盖：

- `I08_RUN_ROOT/I08_JOB_MANIFEST.json`
- `I08_RUN_ROOT/I08_RESULT_MANIFEST.json`
- `I08_RUN_ROOT/I08_ATOMIC_STABILITY_AUDIT.json`
- `I08_POSTPROCESS/I08_43CASE_ACCEPTANCE.json`
- `I08_POSTPROCESS/I08_43CASE_SHA256SUMS.txt`

## 错误日志

- `I08_RUN_ROOT/I08_ERROR_LOG.md`
- `I08_RUN_ROOT/ERROR_LOG.md`
- `agentic_kg/artifacts/I08_KG_ERROR_LOG.md`
- `PDF_CHAPTER2_WORK/CHAPTER2_PDF_ERROR_LOG.md`
- `I06_CHAPTER2_CONTENT/CHAPTER2_CHINESE_CONTENT_BLUEPRINT_ERROR_LOG.md`
- `SUMMARY/I08_DELIVERY_ERROR_LOG.md`

所有失败尝试、同步回写导致的哈希漂移、合同拒绝、PDF 构建/复核异常均保留；最终冻结产物未覆盖这些历史记录。
