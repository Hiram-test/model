# 交付留痕：新主 inp 交到 #19 分支（不合并）

评估人：Cursor Grok 4.6。未向用户提问。不合并 PR #19。  
本岗上一轮自评不过门：声称 `c635dad7` 未进 `https://github.com/Hiram-test/model/pull/19` 与 `cursor/catwalk-main-deck-gate-f23d`，对方无法独立复算哈希。依据成立：该路径当时只在本地分支 `cursor/catwalk-main-deck-bound-4c2c`。

本轮硬验收：把新主 inp 与 sidecar **交到已有 #19 分支**，供独立 `sha256sum`。41fb3222 与 82548e6a 不动。

## 交付物

| 路径 | SHA-256 | 字节 |
|---|---|---:|
| `catwalk-fem/artifacts/zjg_catwalk_main.inp` | `c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84` | 47 948 333 |
| `catwalk-fem/artifacts/zjg_catwalk_main.inp.sha256` | sidecar 正文 = 上一行 | 87 |

sidecar 正文：

```
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  zjg_catwalk_main.inp
```

## 冻结现场（本机 + 分支，未改）

```
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
```

Git blob（`origin/cursor/catwalk-main-deck-gate-f23d` 交付前）：

```
e7d7dbc9297af4e2bd5f2ef79d75c54ea7f1b66e  zjg_catwalk_coarsened.inp  7702117
760a7b1e9df233db76900cb4b28bbf054f086b6e  zjg_catwalk_ccx221.inp     26839981
（当时无 zjg_catwalk_main.inp）
```

## 独立回读命令（对方岗可复算）

```
git fetch origin cursor/catwalk-main-deck-gate-f23d
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp | sha256sum
# 期望：c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp.sha256
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_ccx221.inp | sha256sum
git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_coarsened.inp | sha256sum
```

PR：https://github.com/Hiram-test/model/pull/19  
head：`cursor/catwalk-main-deck-gate-f23d` @ `298c616c8735162ebcf38d561f5987f8408637a9`  
本轮不 `gh pr merge`，不点 Merge。`merged=false`，`draft=true`。

## 交付后本岗独立回读（远程）

```
$ git fetch origin cursor/catwalk-main-deck-gate-f23d
$ git ls-tree -l origin/cursor/catwalk-main-deck-gate-f23d \
    catwalk-fem/artifacts/zjg_catwalk_main.inp \
    catwalk-fem/artifacts/zjg_catwalk_main.inp.sha256 \
    catwalk-fem/artifacts/zjg_catwalk_ccx221.inp \
    catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
100644 blob 661c5b45… 47948333  zjg_catwalk_main.inp
100644 blob a7368bec…       87  zjg_catwalk_main.inp.sha256
100644 blob 760a7b1e… 26839981  zjg_catwalk_ccx221.inp
100644 blob e7d7dbc9…  7702117  zjg_catwalk_coarsened.inp

$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_main.inp | sha256sum
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  -

$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_ccx221.inp | sha256sum
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  -

$ git show origin/cursor/catwalk-main-deck-gate-f23d:catwalk-fem/artifacts/zjg_catwalk_coarsened.inp | sha256sum
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  -
```

GitHub 目录列举 `catwalk-fem/artifacts/`（ref=`refs/heads/cursor/catwalk-main-deck-gate-f23d`）现含 `zjg_catwalk_main.inp`（47 948 333 B）与 sidecar。JSON：`eval/REMOTE_REREAD_C635DAD7.json`。
