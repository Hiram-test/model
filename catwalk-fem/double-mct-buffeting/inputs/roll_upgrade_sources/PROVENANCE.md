# 滚转升级参数来源

本目录两份文件从仓库 main 分支复制，仅作为"双索组滚转升级"模型的参数来源，内容未作任何修改。

- `passage_gate_rope_couplings.csv`：复制自 main 分支 `audit/passage_gate_rope_couplings.csv`。
  给出 42 品横通道站门架的实际索接口坐标：每幅 16 根 φ50 承重索（幅心两侧各 8 根，
  横向偏距 ±850…±2670 mm，间距 260 mm）与 6 根 φ54 门架索（±1690/±1950/±2210 mm）。
  升级模型由此取等效双索组半距 b_B = rms(承重索偏距) = 1858.090 mm、
  b_T = rms(门架索偏距) = 1961.522 mm。
- `mass21_spatialized_v2_nodes.csv`：复制自 main 分支 `mass21_spatialized_v2_nodes.csv`
  （质量空间化审计 V2.0 的正式产物，总质量 963.811380787273 t 与空间化前 MCT 二期
  集中质量闭合，误差 1.1e-13 t）。升级模型用它给二期质量赋予真实的横向与竖向位置，
  从而得到客观的幅内滚转惯量；索系分布质量 3144.655527 t 仍由 MCT 单元自重生成。
- `apply_finite_gates_and_passages_v2.inp`：复制自 main 分支 `run/apply_finite_gates_and_passages_v2.inp`
  （legacy 版，SHA-256 `ba9d062e…`）。原凝聚审计记录的哈希 `51dc4dab…` 对应文件不在仓库；
  已用本副本重跑单中心四端口凝聚，与已审计 `H10_gate_passage_condensed.npz` 的 K24
  逐项相对最大差为 0.0（见 `cluster_condensation/cluster_condensation_audit.json`），
  证明其 H10 子结构（699 根 BEAM188、74 条 ALL 刚臂、44 个索接口）与审计版本完全一致。
- `reference_attachment_2_3_table4_1.csv`：复制自 main 分支 `post/reference_attachment_2_3_table4_1.csv`，
  附件 2-3 表 4-1 的 14 行参考频率（仅作对照，不参与建模）。
- `cluster_condensation/`：`code/condense_h10_cluster_ports.py` 的输出——双簇平动端口
  凝聚矩阵（门架 K12、横通道 K24，N/mm）与谱审计 JSON。
- `drawing_evidence/`：从 GitHub Release `zhangjinggao-full-20260729`（archive-0001.tar.zst）
  提取的图纸与附件页证（页面渲染 PNG，未修改）：
  《张靖皋长江大桥南航道桥猫道结构施工设计图》（1225 版，124 页，SHA-256
  `8df26c6b04f652b952e6cdf9575f34e76c8d014cbb61edf0b846c1c75d8bc113`）之
  MD1-04/05（门架底梁与 φ50 索 M14 U 型螺栓连接）、MD4-01（门架总体）、
  MD5-16/17（抱箍夹具与尼龙滚轮支架）；以及附件 2-3
  《施工猫道抗风性能研究报告》（32 页，SHA-256
  `d17d4061c5726c10b88cc80f3f292b16f0dbf3408e032a30840b1bcaad9173d3`，与包 README 记录一致）
  之图 4-1/4-2（计算模型）与图 4-5（TA1 振型）。
  注：用户所指《图纸汇总-2026.08.05.pdf》（175 页）不在 2026-07-29 归档及其 delta（07-30）
  内，应为 08-05 之后的汇总版；如取得，需核证其新增页（特别是横向通道"新增模块"与站位数）。
