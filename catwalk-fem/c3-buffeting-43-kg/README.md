# C3 × 43 工况知识图谱智能体

本目录把 Double‑MCT I08 的 43 工况本体、四智能体链、证据关系和查询方式迁移到 C3。C3 绑定的是已发布的 parser-safe 模型、UCOR6+UCAB3 求解器和 14 阶原生模态结果。

当前 C3 尚无 43 工况抖振响应结果。图谱中的 C3 CaseResponse 全部为 `NOT_MATERIALIZED`；Double‑MCT 的位移、索力、安全比和 150 模态 ROM 数值仅保留来源关系，不进入 C3 响应节点。

## 已交付

| 文件 | 内容 |
|---|---|
| `cases_43.csv` | 43 工况权威清单与 C3 分层 |
| `model_binding.json` | C3 deck、求解器、DAT、14 阶频率和哈希绑定 |
| `modes_c3_ft14.csv` | C3 原生 14 阶模态分类 |
| `wmct_to_c3_mapping.csv` | Double‑MCT → C3 逐类迁移处置 |
| `table41_c3_pairing.csv` | 当前模态配对状态与证据限定 |
| `c3_agent.py` | 图谱生成、四智能体追踪、Doubao 调用与离线回答 |
| `test_c3_agent.py` | 43 工况、172 个决策、图谱端点和模型绑定测试 |
| `C3_BUFFETING_43CASES_KG.md` | 数据流、查询范围和 Demo 说明 |
| `generated/` | 节点、边、JSON 图谱、追踪表、静态 Demo 输出 |

## 四智能体

1. `AuthorityAgent`：确认工况来自锁定的 43 工况清单。
2. `SolverEvidenceAgent`：读取 C3 原生模态证据，并区分“模态已算”与“该风工况响应未算”。
3. `PhysicsBoundaryAgent`：识别平稳映射、非平稳参考和 C3 响应缺口。
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

