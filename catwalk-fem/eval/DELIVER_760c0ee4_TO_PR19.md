# 把 760c0ee4 交到已有 #19 分支（不合并）

评估人：Cursor Grok 4.6。未向用户提问。不合并。c635dad7 不动。41fb3222 不动。

规则（用户原文）：**没进 #19 不算新主。760c0ee4 先交进账本，校验才能独立复算。**

## 交付前不过门依据（本岗复算成立）

交付前 `origin/cursor/catwalk-main-deck-gate-f23d`：

```
$ git ls-tree -l origin/cursor/catwalk-main-deck-gate-f23d \
    catwalk-fem/artifacts/zjg_catwalk_cleared.inp
# 无该路径

$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/checksums.sha256 \
    | grep zjg_catwalk
82548e6a…  zjg_catwalk_coarsened.inp
41fb3222…  zjg_catwalk_ccx221.inp
c635dad7…  zjg_catwalk_main.inp
# 无 zjg_catwalk_cleared.inp
```

GitHub 目录列举无 `zjg_catwalk_cleared.inp`。`HASH_LEDGER.json` 的 `new_main` 仍是 c635dad7。  
因此上一轮声称可在 #19 独立复算 760c0ee4：**不成立**。本岗认同该不过门。

## 本轮交付（已有 #19 分支，不新开 PR）

写到 `cursor/catwalk-main-deck-gate-f23d`：

| 路径 | SHA-256 | 字节 |
|---|---|---:|
| `catwalk-fem/artifacts/zjg_catwalk_cleared.inp` | `760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9` | 47 948 916 |
| sidecar | 第一字段同一字符串 | |

账本 `checksums.sha256` 追加 cleared 两行；`HASH_LEDGER.json` 把 760c0ee4 记为 `new_main`，c635dad7 改记为 `fail_site_four_unconstrained_b31`。  
不改写 `zjg_catwalk_main.inp` / `zjg_catwalk_ccx221.inp` / `zjg_catwalk_coarsened.inp`。

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

账本行与 `git show | sha256sum` 必须同一字符串，才算新主进账。不合并。

## 交付后当场核

```
$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_cleared.inp | sha256sum
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  -
```

JSON：`eval/REMOTE_REREAD_760c0ee4.json`。PR `merged=false`。
