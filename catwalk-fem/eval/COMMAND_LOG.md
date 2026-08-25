# 命令留痕（本 run，不找用户）

评估人：Cursor Grok 4.6。工作目录 `/workspace`。

## 本轮：把 760c0ee4 交到 #19 分支（不合并）

```
$ git fetch origin cursor/catwalk-main-deck-gate-f23d
$ git ls-tree -l origin/cursor/catwalk-main-deck-gate-f23d \
    catwalk-fem/artifacts/zjg_catwalk_cleared.inp
# 交付前：无该路径（不过门依据）

$ git checkout cursor/catwalk-main-deck-gate-f23d
$ git checkout cursor/catwalk-clear-four-4c2c -- \
    catwalk-fem/artifacts/zjg_catwalk_cleared.inp \
    catwalk-fem/artifacts/zjg_catwalk_cleared.inp.sha256 \
    catwalk-fem/artifacts/checksums.sha256 \
    catwalk-fem/artifacts/HASH_LEDGER.json
# 未 checkout 三张冻结 .inp

$ sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp \
            catwalk-fem/artifacts/zjg_catwalk_ccx221.inp \
            catwalk-fem/artifacts/zjg_catwalk_main.inp \
            catwalk-fem/artifacts/zjg_catwalk_cleared.inp
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  catwalk-fem/artifacts/zjg_catwalk_main.inp
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  catwalk-fem/artifacts/zjg_catwalk_cleared.inp
```

未改写 c635dad7 / 41fb3222。不 merge。

---

## 上一轮：清 4 个无约束 B31 分量（不 push，不交计算）

```
$ git checkout -b cursor/catwalk-clear-four-4c2c
$ python3 catwalk-fem/pipeline/clear_four_b31.py
{
  "dest_sha256": "760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9",
  "dest_bytes": 47948916,
  "after_n_unconstrained_components": 0,
  "frozen_untouched": {"82548e6a": true, "41fb3222": true, "c635dad7": true},
  "ccx_ran": false
}

$ python3 catwalk-fem/pipeline/reread_cleared.py
pass=true  c635_unc=4  cleared_unc=0  ic_n_rows=421432
e_cross_passage=42  drawing_stubs=28  eight_ips=true

$ python3 catwalk-fem/tests/test_clear_four_b31.py
test_clear_four_b31 ok
$ python3 catwalk-fem/tests/test_audit_frozen_deck.py
test_audit_frozen_deck ok
$ python3 catwalk-fem/tests/test_new_main_deck.py
test_new_main_deck ok
$ python3 catwalk-fem/tests/test_coord_gate.py
test_coord_gate ok
$ python3 catwalk-fem/tests/test_write_inp.py
test_write_inp ok
$ python3 catwalk-fem/tests/test_reconcile.py
test_reconcile ok

$ sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp \
            catwalk-fem/artifacts/zjg_catwalk_ccx221.inp \
            catwalk-fem/artifacts/zjg_catwalk_main.inp \
            catwalk-fem/artifacts/zjg_catwalk_cleared.inp
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  catwalk-fem/artifacts/zjg_catwalk_main.inp
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  catwalk-fem/artifacts/zjg_catwalk_cleared.inp

$ grep zjg_catwalk catwalk-fem/artifacts/checksums.sha256
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  zjg_catwalk_ccx221.inp
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  zjg_catwalk_main.inp
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  zjg_catwalk_cleared.inp
```

$ cd catwalk-fem/paper && pdflatex -interaction=nonstopmode zjg_catwalk_agentic_fea.tex
Output written on zjg_catwalk_agentic_fea.pdf (11 pages, 281162 bytes).

未运行 `ccx`。未 `git push`。未 merge。

---

评估人：Cursor Grok 4.6。工作目录 `/workspace`。

## 本轮：把 c635dad7 交到 #19 分支（不合并）

```
$ git fetch origin cursor/catwalk-main-deck-gate-f23d
$ git ls-tree -l origin/cursor/catwalk-main-deck-gate-f23d \
    catwalk-fem/artifacts/zjg_catwalk_main.inp
# 交付前：无该路径（不过门依据）

$ git checkout cursor/catwalk-main-deck-gate-f23d
$ sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp \
            catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  catwalk-fem/artifacts/zjg_catwalk_ccx221.inp

$ git checkout cursor/catwalk-main-deck-bound-4c2c -- \
    catwalk-fem/artifacts/zjg_catwalk_main.inp \
    catwalk-fem/artifacts/zjg_catwalk_main.inp.sha256 \
    catwalk-fem/paper/zjg_catwalk_agentic_fea.md \
    catwalk-fem/paper/zjg_catwalk_agentic_fea.tex \
    catwalk-fem/paper/zjg_catwalk_agentic_fea.pdf \
    catwalk-fem/eval/DEFINITION_TABLE_41fb3222.md \
    catwalk-fem/eval/HASHES_THIS_RUN.sha256 \
    catwalk-fem/eval/SINGULAR_DEFS_41fb3222.json \
    catwalk-fem/eval/SINGULAR_DEFS_c635dad7.json

$ sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp \
            catwalk-fem/artifacts/zjg_catwalk_ccx221.inp \
            catwalk-fem/artifacts/zjg_catwalk_main.inp
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  catwalk-fem/artifacts/zjg_catwalk_main.inp
```

```
$ git push -u origin cursor/catwalk-main-deck-gate-f23d
215bb01..298c616  cursor/catwalk-main-deck-gate-f23d -> cursor/catwalk-main-deck-gate-f23d

$ git fetch origin cursor/catwalk-main-deck-gate-f23d
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp | sha256sum
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  -
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_ccx221.inp | sha256sum
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  -
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_coarsened.inp | sha256sum
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  -
```

PR #19 head=`298c616`，`merged=false`。不 merge。

## 账本登记 c635dad7（checksums.sha256 + HASH_LEDGER.json）

交付前 `checksums.sha256` 无 `zjg_catwalk_main.inp`。本轮追加两行，不改 82548e6a / 41fb3222 行。

```
$ grep zjg_catwalk catwalk-fem/artifacts/checksums.sha256
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  zjg_catwalk_ccx221.inp
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  zjg_catwalk_main.inp
```

---

评估人：Cursor Grok 4.6。工作目录 `/workspace`。分支 `cursor/catwalk-main-deck-gate-f23d`。

## 冻结 deck 未改

```
$ sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
```

发射新 deck 之后再跑一次，哈希相同。

冻结 IC（独立 `sed`/`python` 回读，第 90863–90865 行）：

```
*INITIAL CONDITIONS, TYPE=STRESS
E_FLOOR_ROPE, 3.549611e+08
E_PORTAL_ROPE, 2.426295e+08
```

## 写入器与发射

```
$ python3 catwalk-fem/tests/test_coord_gate.py
test_coord_gate ok
$ python3 catwalk-fem/tests/test_write_inp.py
test_write_inp ok
$ python3 catwalk-fem/tests/test_reconcile.py
test_reconcile ok
$ python3 catwalk-fem/tests/test_audit_frozen_deck.py
test_audit_frozen_deck ok
$ python3 catwalk-fem/pipeline/emit_new_main_deck.py
{
  "frozen_untouched": true,
  "new_sha256": "41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a",
  "new_bytes": 26839981,
  "ic_n_rows": 204208,
  "all_ccx221_legal": true,
  "any_elset_uniaxial": false,
  "gate_status": "PASS",
  "failed": []
}
$ python3 catwalk-fem/tests/test_new_main_deck.py
test_new_main_deck ok
```

中间一次发射（旧梁轴）哈希 `48c7f304e9e47227217390d8db032ee6d0c828e41c54e9b6c31177fc724e7a14`，现场 `eval/ccx_48c7f304/`。正式新主 deck 覆盖写为 `41fb3222`。

## 新 deck IC 词法（独立回读）

```
90873: *INITIAL CONDITIONS, TYPE=STRESS
90874: 1, 1, 1.439957e+08, 0.000000e+00, 2.109655e+08, 0.000000e+00, 1.742932e+08, 0.000000e+00
...
（8 个积分点重复同一全局 PK2）
295082: *STEP, NLGEOM
IC data rows: 204208
tr(S) = 3.549612e+08 Pa = sigma_floor
```

## CalculiX 2.21

```
$ ccx -v
This is Version 2.21
```

副本目录 `/tmp/ccx-41fb3222/`，`job.inp` sha256 = `41fb3222…bbca924a`。

```
exit_code 255
wall_s    10.35
parse_fail_ic false
number of equations 879076
spooles.out: matrix found to be singular
```

诊断：全约束 51 896 个原节点后矩阵不再奇异（`/tmp/ccx-diag-pinall`，exit 201，未收敛，因过约束+预应力不兼容）。连通性见 `eval/connectivity_audit.json`。

## 小算例（格式合同）

`/tmp/ccx-toy/`：ELSET+单轴 → exit 201，卡图 `E1, 3.549611e+08`。  
八字段 1 积分点或 8 积分点 + 两端固结线性静力 → exit 0，四件套非空。

## 用字更正（本轮）

用户更正：`142 榀门架对账（不是榌）`。  
单位：榀（U+6980）。禁止：榌（U+698C）。  
不再把榌写成�单位：榀（U+6980）。禁止：榌（U+698C）。  
不再把榌写成榀的变体。  
两份 deck 哈希未改：`82548e6a` 与 `41fb3222`。  
`41fb3222` 标题行仍写「not 槇」——那是上一轮写入器注释；本轮不为改一个字重写 26 MB 主 deck。  
写入器源码 `write_inp.py` 已改为 `not 榌 U+698C`，只影响以后再发射。
