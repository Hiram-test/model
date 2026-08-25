# catwalk-fem

张靖皋施工猫道的 STEP → CalculiX `.inp` 管线，并执行坐标过门
\(x=\text{桩号}-K16+876.000\)。面层锚与门架锚分开。21 道横通道。**142 榀门架**（不是槇）。

几何只来自 Release `catwalk-attachment23-v2.0-s10-20260716` 的中心线 STEP。
材料、索力和工况来自图纸/复核报告。禁止读取同 Release 的 S10 `.db`。

冻结失败现场：`artifacts/zjg_catwalk_coarsened.inp`  
SHA-256 `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da`（**不改**）。  
该文件的 `TYPE=STRESS` 是 ELSET+单轴。

新主 deck：`artifacts/zjg_catwalk_ccx221.inp`  
SHA-256 `41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a`。  
`TYPE=STRESS` 为单元号+积分点+六全局 PK2（204 208 行）。  
CalculiX 2.21 读入成功，组装 879 076 方程，切线奇异（22 096 个不连通分量）。  
四件套：`artifacts/ccx_41fb3222.{frd,dat,sta,cvg}`。

完整论文：`paper/zjg_catwalk_agentic_fea.md`（中文正本）、`.tex`、`.pdf`。  
自评留痕：`eval/GROK_SELF_EVAL.md`。

```bash
python3 catwalk-fem/tests/test_coord_gate.py
python3 catwalk-fem/tests/test_write_inp.py
python3 catwalk-fem/tests/test_reconcile.py
python3 catwalk-fem/tests/test_audit_frozen_deck.py
python3 catwalk-fem/tests/test_new_main_deck.py
python3 catwalk-fem/pipeline/emit_new_main_deck.py
sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
sha256sum catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
```

不要把 77 MB STEP 入库。不要把 `isolated/TARGET-FREQ.json` 喂给写入器。
不要改写 `zjg_catwalk_coarsened.inp`。
