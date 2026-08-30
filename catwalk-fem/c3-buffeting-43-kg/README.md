# C3 × 43 工况知识图谱智能体

本目录把 Double‑MCT I08 的 43 工况本体、四智能体规则、证据关系和来源链迁移到 C3。C3 绑定的是已发布的 parser-safe 模型、UCOR6+UCAB3 求解器和 14 阶原生模态结果。

模型迁移已经完成，但这不等于 C3 原生的 43 工况抖振响应已经计算。图谱中的 C3 `CaseResponse` 全部为 `NOT_MATERIALIZED`；Double‑MCT 的位移、索力、安全比和 150 模态 ROM 数值仅保留来源关系，不进入 C3 响应节点。

## 模型迁移验收范围

- 完整保留 I08 的 43 行 × 37 字段源权威矩阵作为 provenance；C3 分类是独立 overlay，不回写源权威。
- 源 CSV 的原始 CRLF 文件 SHA‑256 为 `12673049d2cfae885fb5a35d855441e7385b644d1182a7cc020d5e49f5e28b7f`；仓库内 LF 规范化副本 SHA‑256 为 `95fe97e73b3bec61124147b9c29a4ed3abf6217537e8bf082eca707426f3625a`。两者内容等价但字节哈希不同。
- `source_case_index` 保留 I08 原始顺序，`c3_order` 表示 C3 展示顺序；两列不得互相替代。
- 源分类为 35 个 `stationary_ok`、8 个 `reference_only`；C3 策略为 33 个 `stationary_eligible`、10 个 `envelope_only`。仅 `cape_denison_katabatic` 和 `piteraq_tasiilaq` 两个工况在 C3 overlay 中改为 envelope-only。
- 源包 36 个资产已逐项盘点并绑定 Git blob、SHA‑256、大小和处置方式；迁移不复制任何旧数值为 C3 结果。
- 旧图谱的 2,064 个数值 `MetricObservation` 有意不迁移；它们仍属于 Double‑MCT 结果，不是 C3 证据。
- `table41_c3_pairing.csv` 中的四项仅是 `NOT_ALIGNED` 比较候选，不是工作配对；在绑定可复核的 80 阶 C3 模态产物前，不得作为已确认配对。

## 已交付

| 文件 | 内容 |
|---|---|
| `cases_43.csv` | 43 工况权威清单与 C3 分层 |
| `authority/I08_GITHUB_43_CASE_MATRIX.csv` | 43 × 37 源权威矩阵的 LF 规范化 provenance 副本 |
| `case_migration_matrix.csv` | 源顺序、C3 顺序、源分类与 C3 overlay 的逐工况映射 |
| `source_asset_inventory.json` | Double‑MCT 源包 36 个资产的完整盘点和迁移处置 |
| `agent_policy_c3.json` | 四智能体迁移契约、禁止声明和输出边界 |
| `model_binding.json` | C3 deck、求解器、DAT、14 阶频率和哈希绑定 |
| `modes_c3_ft14.csv` | C3 原生 14 阶模态分类 |
| `wmct_to_c3_mapping.csv` | Double‑MCT → C3 逐类迁移处置 |
| `table41_c3_pairing.csv` | 明确未对齐的模态比较候选与证据限定 |
| `c3_agent.py` | 图谱生成、四智能体追踪、Doubao 调用与离线回答 |
| `test_c3_agent.py` | 权威映射、迁移边界、图谱完整性和模型绑定测试 |
| `C3_BUFFETING_43CASES_KG.md` | 数据流、查询范围和 Demo 说明 |
| `generated/` | 图谱、追踪表、迁移验收、校验结果和 Demo 输出 |

## 四智能体

1. `AuthorityAgent`：确认工况来自锁定的 43 × 37 源权威矩阵，并同时保留源顺序与 C3 顺序。
2. `SolverEvidenceAgent`：读取 C3 原生模态证据，并区分“模态已算”与“该风工况响应未算”。
3. `PhysicsBoundaryAgent`：分离源平稳性和 C3 eligibility overlay，并识别 C3 响应缺口。
4. `WarningPolicyAgent`：输出证据状态；当前 43/43 为 `NOT_ARMED`、`dispatch=false`。

Doubao 负责把结构化查询结果组织成自然语言。确定性智能体先生成事实包，Doubao 不改写图谱状态，也不把旧模型数值写成 C3 结果。

## 直接运行

```bash
python c3_agent.py build
python c3_agent.py validate
python c3_agent.py ask --case site_gb50009_100yr --question "这个工况在 C3 上有什么证据？"
python c3_agent.py ask --case piteraq_tasiilaq --question "为什么只能作为非平稳参考？" --output generated/demo_piteraq.json
```

有 Doubao Key 时自动调用火山方舟；无 Key 时使用同一事实包生成离线回答。程序依次读取 `DOUBAO_API_KEY`、`DOUBAO_API`、`ARK_API_KEY`、`VOLCENGINE_API_KEY`。默认 Base URL 为 `https://ark.cn-beijing.volces.com/api/v3`，默认模型为 `doubao-seed-1-8-251228`，均可通过环境变量覆盖。

```bash
export DOUBAO_API_KEY="<repository secret at runtime>"
export DOUBAO_MODEL="doubao-seed-1-8-251228"
python c3_agent.py ask --case meranti_2016_peak --question "按证据链说明这个工况" --require-llm
```

GitHub Actions 工作流 `.github/workflows/c3-43kg-doubao-demo.yml` 会自动完成构图、校验、测试、离线 Demo，并在检测到仓库中的任一支持 Key 时追加真实 Doubao Demo。API Key 只由 Actions Secret 注入，不写入代码、日志或产物。

## C3 数值边界

- C3 deck：`C3-UB-FT14-PARSER-SAFE_m14_667c504770b99d4a.inp`
- Deck SHA‑256：`667c504770b99d4a3c484a114e16bb7c048c883d3a004f3e10dd71536f33dc86`
- 求解器：CalculiX 2.23 + UCOR6 + UCAB3 + FT14 shift
- 求解器 SHA‑256：`b498dad80b0415d53ab112409adc85b8a1fd19eb7846dc31e778f4c83b437a0e`
- 原生结果：91,415 节点、172,998 单元、439,122 活跃方程、14 阶模态
- 当前用途：C3 图谱查询与证据推演 Demo
- 当前缺口：C3 风荷载映射、响应 ROM/直接求解、43 工况响应结果
- 验收结论：语义、权威、规则、来源和 C3 模型绑定迁移完成；C3 原生响应计算不在本次迁移完成声明内
