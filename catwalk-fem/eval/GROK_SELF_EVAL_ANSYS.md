# 留痕（从零 MCT；对照 ANSYS；不编）

评估人：Cursor Grok 4.6。未向用户提问。不 push。不合并。`760c0ee4` 不动。不是科学结论。

| 用户句 | 本岗 | 依据 |
|---|---|---|
| 预应力在 MCT | **成立** | `*INIFORCE` 1123 eid；`*INI-EFORCE` 1123；从 `.mct` 正文 |
| 从零复现先做 | **成立** | `catwalk-fem/mct-from-zero/` 读 MCT 体，不用归档 CSV 当新主 |
| 对照 ANSYS | **`.db` 抽出失败，留痕迹** | 无 MAPDL；158568 串，INISTATE/LINK180/PRESTRESS 均为 0 |
| 先静力 / 索力 / 预应力 | **MCT 侧已迁出静力 inp** | `mct_from_zero_static.ccx.inp`；索力来自 MCT，不是编的 |
| 只迁，不编 | **成立** | 未手写索力表；抽不出的 ANSYS 数保持 null |
| 不 push | **成立** | 只写本地 `#19` 分支 |
| `760c0ee4` 不动 | **成立** | sha256 仍 `760c0ee4…85de9` |
| 没进 #19 远程不算新主 | **本轮不算新主** | 不 push |

当场：

```
0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1  猫道 - 门架索合建模型2.mct
17e0bac8717e7c32a407571d33e38dd777736b31b6656684e53449fa8c9d40fd  cw_S10_0716t050342_a4_eq.db
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  zjg_catwalk_cleared.inp
```

APDL/oracle 的 LINK180 数只标成归档快照，**不是** `.db` POST1。MCT 与 S10 网格不同，没有 1:1。
