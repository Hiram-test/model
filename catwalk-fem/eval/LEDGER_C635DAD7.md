# 账本登记：c635dad7 进 #19（不合并）

评估人：Cursor Grok 4.6。未向用户提问。不合并。41fb3222 不动。

规则（用户原文）：**没进 #19 不算新主。c635dad7 先交进账本，校验才能独立复算。**

## 交付前账本缺口

`artifacts/checksums.sha256`（#19 上的哈希账本）交付前只有：

```
82548e6a…  zjg_catwalk_coarsened.inp
41fb3222…  zjg_catwalk_ccx221.inp
```

**没有** `zjg_catwalk_main.inp` / `c635dad7`。  
`main_deck_manifest.json` 仍指向 82548e6a。  
因此即令 inp 字节已在分支上，账本未登记，独立复算对不上「新主」条目。

## 本轮写入账本（不改冻结两行）

`artifacts/checksums.sha256` 追加：

```
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  zjg_catwalk_main.inp
54bd94faf06f2265d3878859d425cd58a8f474d4d8f2760dbe4ee75cbb9f06d9  zjg_catwalk_main.inp.sha256
```

角色账本：`artifacts/HASH_LEDGER.json`（三行：82548e6a 失败现场 / 41fb3222 奇异现场 / c635dad7 新主）。

## 独立复算命令

```
git fetch origin cursor/catwalk-main-deck-gate-f23d
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/checksums.sha256 | grep zjg_catwalk
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/HASH_LEDGER.json
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp | sha256sum
# 期望：c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_ccx221.inp | sha256sum
# 期望：41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a
```

账本行与 `git show | sha256sum` 必须同一字符串，才算新主进账。

## 交付后本岗独立回读

```
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/checksums.sha256 | grep zjg_catwalk_main.inp
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  zjg_catwalk_main.inp
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp | sha256sum
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  -
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_ccx221.inp | sha256sum
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  -
```

GitHub `get_file_contents` 对 `checksums.sha256` 与 `HASH_LEDGER.json` 同一字符串。账本行 = 独立 `sha256sum`。41fb3222 未改。PR `merged=false`。
