# C3 抖振 × 43 工况知识图谱包

状态：`REVIEW_ONLY` / `BOUNDED_REFERENCE`  
Schema：`catwalk-c3-kg/v1`  
对象：张靖皎南航道桥施工猫道 `C3.inp`  
声明：inventory graph of the WMCT→C3 remap; **not a scientific conclusion**。C3 尚未写入风步，不得写成已复现附件表 5-1。

## 文件

| 文件 | 用途 |
|---|---|
| `C3_BUFFETING_43CASES_KG.md` | 完整说明 |
| `knowledge_graph_c3.json` | 机器可读图谱 |
| `knowledge_graph_c3_nodes.csv` | 节点 |
| `knowledge_graph_c3_edges.csv` | 边 |
| `cases_43.csv` | 43 工况全表 + C3 分层 |
| `wmct_to_c3_mapping.csv` | WMCT/true3d → C3 对照 |
| `table41_c3_pairing.csv` | 附件表 4-1 ↔ C3-FT14 |

## 正确用途

- 查阅 C3 集合如何承接抖振核与 43 条 U10
- 查阅哪些旧边必须切断
- 作为后续写 C3 `*CLOAD/*DLOAD` 的清单

## 不正确用途

- 当作 C3 已经算完抖振
- 把 ROM 跨中 47.9 m / 安全比 3.13 抄到 C3
- 用平稳谱复现龙卷 / 下击暴流 / 皮特拉克
