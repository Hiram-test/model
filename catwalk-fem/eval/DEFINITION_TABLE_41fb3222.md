# 41fb3222 独立复算定义表（本岗）

评估人：Cursor Grok 4.6。未向用户提问。未改 `zjg_catwalk_ccx221.inp`。不 push。

现场：`catwalk-fem/artifacts/zjg_catwalk_ccx221.inp`  
SHA-256 `41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a`  
26 839 981 字节。角色：IC 读入过门 / 第一增量奇异现场。**不动。**

命令：

```
$ sha256sum catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
$ python3 catwalk-fem/tests/test_singular_defs.py
test_singular_defs ok
$ python3 catwalk-fem/pipeline/singular_audit.py catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
match_given.all = true
```

JSON：`eval/SINGULAR_DEFS_41fb3222.json`。

| 量 | 值 | 含义 |
|---|---:|---|
| 使用节点连通分量 | **22096** | used-node connected components |
| 2 节点碎片 | **19371** | size-2 components |
| 其中 T3D2 | **17756** | floor_rope 17616 + portal_rope 136 + handrail_rope 4 |
| 其中 B31 | **1615** | portal_or_beam 1594 + cross_passage 21 |
| 无约束**分量** | **21426** | 分量里**没有任何**约束节点。不是无约束节点个数 |
| 无约束**节点** | **50676** | 51896 − 1220 |
| 三张锚并集 | **1220** | `N_FLOOR_ANCHOR` 312 ∪ `N_PORTAL_ANCHOR` 16 ∪ `N_SUPPORT_SADDLE_ENDS` 904；面层∩门架 = 0 |
| 节点 | 51896 | |
| 单元 | 30317 | |

恒等式（本机复算）：

```
19371 = 17756 + 1615
50676 = 51896 − 1220
21426 ≠ 50676
```

禁止写法：把 21426 写成「21426 个无约束节点」。
