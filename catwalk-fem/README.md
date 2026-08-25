# catwalk-fem

张靖皋施工猫道的 STEP → CalculiX `.inp` 管线，并执行坐标过门
\(x=\text{桩号}-K16+876.000\)。面层锚与门架锚分开。21 道横通道。**142 榀门架**（不是槬）。

几何只来自 Release `catwalk-attachment23-v2.0-s10-20260716` 的中心线 STEP。
材料、索力和工况来自图纸/复核报告。禁止读取同 Release 的 S10 `.db`。

冻结主 deck：`artifacts/zjg_catwalk_coarsened.inp`  
SHA-256 `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da`（**不改**）。

CalculiX 2.21 已在该哈希的副本上跑过：读入 `*INITIAL CONDITIONS` 失败
（`E_FLOOR_ROPE,3.549611E+08`，exit 201）。无 `.frd`，`.dat` 空，`.sta`/`.cvg` 仅表头。
该 deck 的 `TYPE=STRESS` 是 ELSET+单轴；ccx 2.21 要单元号+积分点+六应力。

完整论文：`paper/zjg_catwalk_agentic_fea.md`（中文正本）、`.tex`、`.pdf`。

```bash
python3 catwalk-fem/tests/test_coord_gate.py
python3 catwalk-fem/tests/test_write_inp.py
python3 catwalk-fem/tests/test_reconcile.py
python3 catwalk-fem/tests/test_audit_frozen_deck.py
python3 catwalk-fem/pipeline/audit_frozen_deck.py
sha256sum -c catwalk-fem/artifacts/zjg_catwalk_coarsened.inp.sha256
```

不要把 77 MB STEP 入库。不要把 `isolated/TARGET-FREQ.json` 喂给写入器。
