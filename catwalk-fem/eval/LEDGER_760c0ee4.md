# 账本登记：760c0ee4 进 #19（不合并）

评估人：Cursor Grok 4.6。未向用户提问。不合并。c635dad7 不动。41fb3222 不动。

规则（用户原文）：**没进 #19 不算新主。760c0ee4 先交进账本，校验才能独立复算。**

## 交付前账本缺口

`artifacts/checksums.sha256`（#19 上的哈希账本）交付前只有：

```
82548e6a…  zjg_catwalk_coarsened.inp
41fb3222…  zjg_catwalk_ccx221.inp
c635dad7…  zjg_catwalk_main.inp
```

**没有** `zjg_catwalk_cleared.inp` / `760c0ee4`。  
`HASH_LEDGER.json` 的 `new_main` 仍指向 c635dad7。  
因此即令本地有字节，账本未在 #19 远程登记，独立复算对不上「新主」条目。

## 本轮写入账本（不改冻结三行）

`artifacts/checksums.sha256` 追加：

```
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  zjg_catwalk_cleared.inp
6ef1ee91f925d2757a55e6c4427e34ac67062cafbc382dc3aee26e59e776b613  zjg_catwalk_cleared.inp.sha256
```

82548e6a / 41fb3222 / c635dad7 三行未改。  
角色账本：`artifacts/HASH_LEDGER.json`（82548e6a 失败现场 / 41fb3222 奇异现场 / c635dad7 四分量不过门现场 / 760c0ee4 新主）。

## 独立复算命令

```
git fetch origin cursor/catwalk-main-deck-gate-f23d
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/checksums.sha256 | grep zjg_catwalk
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/HASH_LEDGER.json
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_cleared.inp | sha256sum
# 期望：760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp | sha256sum
# 期望：c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_ccx221.inp | sha256sum
# 期望：41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a
```

账本行与 `git show | sha256sum` 必须同一字符串，才算新主进账。

## 交付后本岗独立回读

```
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/checksums.sha256 | grep zjg_catwalk_cleared.inp
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  zjg_catwalk_cleared.inp
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_cleared.inp | sha256sum
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  -
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp | sha256sum
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  -
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_ccx221.inp | sha256sum
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  -
```

GitHub `get_file_contents` 对 `checksums.sha256` 与 `HASH_LEDGER.json` 同一字符串。账本行 = 独立 `sha256sum`。c635dad7 / 41fb3222 未改。PR `merged=false`。
