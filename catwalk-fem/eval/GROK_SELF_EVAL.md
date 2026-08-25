# Grok 自评留痕（catwalk-main-deck-gate-f23d，新主 deck）

评估人：本 run 的模型（Cursor Grok 4.6）。未向用户提问。未 push。  
依据只引用本仓库文件、本机命令输出、CalculiX 2.21 手册 §7.76。  
门架计数单位：**榀（U+6980）**。不是槇（U+69C7）。本轮用户写「142 榌门架」（U+698C），视为榀的输入变体，不另开账。

## 1. 任务理解（先写依据）

| 用户句 | 我当作硬验收 | 依据 |
|---|---|---|
| 新主 deck 按这个依据改 | 另写新哈希 deck；`write_inp.py` 发射 §7.76 | 用户原文 |
| 82548e6a 的 TYPE=STRESS 是 ELSET+单轴 | 冻结文件第 90863–90865 行保持原样 | 用户原文；本机 `sha256sum` |
| 对不上 ccx 2.21 §7.76（单元号+积分点+六 PK2） | 新 deck 每行 8 字段，全局第二类 Piola–Kirchhoff | 手册 p.529–530 |
| 未改该 deck | 运行前后 `82548e6a…276ab6da` | 用户原文 |
| 留痕 `catwalk-fem/eval/` | 本文件 + JSON + ccx 副本 | 用户原文 |
| 不许找用户 / 不 push | 全程不提问；只本地 commit | 用户原文 |
| \(x=\)桩号\(-K16+876\) | 节点/边界/荷载同一公约 | SKILL 硬约束 |
| 面层锚和门架锚分开 | `N_FLOOR_*` ∩ `N_PORTAL_*` = ∅ | 用户原文 |
| 21 道横通道 | 对账 21/21，插入 0 | theory v1.2 |
| 142 榀门架（不是槇；本轮写榌） | 71×2=142，单位 U+6980 | 用户更正 + 本轮原文 |
| 产出完整论文才算结束 | `paper/*.md` + `.tex` + PDF | 原任务 |

不把「矩阵可分解 / 位移已求出」写成已给条件。已给条件停在：旧卡不合法、要新主 deck、要留痕。

## 2. 本 run 实际做了什么

1. 核分支 `cursor/catwalk-main-deck-gate-f23d`。当场重算冻结哈希 = `82548e6a…276ab6da`。
2. 改 `pipeline/write_inp.py`：`TYPE=STRESS` 改为单元号、积分点 1–8、六全局 PK2（\(S=\sigma\,n\otimes n\)）。不再发射 ELSET+单轴。
3. 从冻结 deck **只读**回读网格（不读 77 MB STEP，不写回 82548e6a），调用同一写入器，交出新主 deck `artifacts/zjg_catwalk_ccx221.inp`。
4. 独立回读新 deck：204 208 行全部 `ccx_2_21_legal`，首行迹 = \(\sigma_{\mathrm{floor}}\)。
5. 加门 `IC-G-ccx221-pk2`。新 deck 27/27 PASS。
6. 本机 CalculiX 2.21 在新哈希的副本上求解。读入成功。组装 **879 076** 个方程。SPOOLES：`matrix found to be singular`，exit 255。
7. 独立连通性审计：粗化中心线 **22 096** 个连通分量（最大 129 节点）。这是切线奇异的结构原因，不是 IC 词法。
8. 写出完整论文（中文 md + 英文 tex + PDF）。本文件留痕。不 push。

中间哈希 `48c7f304` 是同一 IC 格式、旧梁轴 \(n_1=(0,0,1)\)、默认步长的第一次合法发射；同样读入成功、同样 879 076 方程、同样奇异。现场在 `eval/ccx_48c7f304/`。正式新主 deck 是 `41fb3222`（梁轴 \(n_1=(1,1,1)\)，`*STATIC` 写出增量）。

## 3. 过门证据（可复核命令）

### 3.1 冻结哈希未改

```
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
```

`eval/new_deck_reread.json`：`frozen_before == frozen_after == FROZEN_SHA256`。  
第 90863–90865 行仍是：

```
*INITIAL CONDITIONS, TYPE=STRESS
E_FLOOR_ROPE, 3.549611e+08
E_PORTAL_ROPE, 2.426295e+08
```

### 3.2 新主 deck

```
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  catwalk-fem/artifacts/zjg_catwalk_ccx221.inp
```

26 839 981 字节。与 82548e6a **不同**。

独立回读（`eval/new_deck_reread.json`）：

```
ic_n_rows              204208
n_ccx221_legal         204208
n_elset_uniaxial       0
first_tokens           单元号
first_row              1, 1, 1.439957e+08, 0, 2.109655e+08, 0, 1.742932e+08, 0
trace                  3.549612e+08  == sigma_floor（8 积分点重复）
heading                x = chainage - K16+876.000
N_FLOOR_ANCHOR         312
N_PORTAL_ANCHOR        16
overlap                0
*BOUNDARY              三张独立卡
255.56 / 0.0296        不在正文
```

204 208 = (25 299 面层 + 227 门架索) × 8 积分点。T3D2 按手册 §6.2.35 随 B31 扩成 C3D8I。

### 3.3 单元测试

```
test_coord_gate ok
test_write_inp ok
test_reconcile ok
test_audit_frozen_deck ok
test_new_main_deck ok
```

### 3.4 142 榀门架（不是槇）

`portal_142_ledger.json` / `audit_frozen_deck.py`：

```
expected_per_deck     71
expected_both_decks   142
upstream_hit          71
downstream_hit        71
both_decks_hit        142
n_missing             0
inserted_portals      0
by_span               north_660=11, main_2300=41, south_717=11, south_503=8
unit                  榀
not_unit              槇
pass_142              true
```

21/21 横通道，插入 0。面层/门架锚交集空。

### 3.5 CalculiX 2.21 对新哈希

```
$ ccx -v
This is Version 2.21

副本 sha256 = 41fb3222…bbca924a
exit 255
wall_s = 10.35
parse_fail_ic = false
number of equations = 879076
spooles.out = "matrix found to be singular"
```

四件套（`artifacts/ccx_41fb3222.*`）：

| 文件 | 字节 | 内容 |
|---|---:|---|
| `.frd` | 80 | 标题行，无位移块 |
| `.dat` | 42 | `STEP 1` 表头 |
| `.sta` | 98 | 仅 SUMMARY 表头 |
| `.cvg` | 274 | 仅收敛表头 |

与 82548e6a 的对比：旧哈希在读入第一行 IC 就 exit 201，无方程数，墙钟 <1 s，无 `.frd`。新哈希读入成功、有方程数、有 `.frd` 头、然后在分解时因奇异退出。

连通性（`eval/connectivity_audit.json`）：22 096 分量，度 1 节点 43 468，最大分量 129 节点。全约束原节点的诊断副本（`/tmp/ccx-diag-pinall`）矩阵不再奇异，说明奇异来自未连成整体的中心线机构，不是 IC 八字段。

未加虚构弹簧，未把不连通碎片焊成一张网。那会改变几何主张。

### 3.6 论文

| 文件 | 结果 |
|---|---|
| `paper/zjg_catwalk_agentic_fea.md` | 中文十章 + 附录 |
| `paper/zjg_catwalk_agentic_fea.tex` | 英文十章 |
| `paper/zjg_catwalk_agentic_fea.pdf` | `pdflatex` 两遍 exit 0，10 页，266 464 字节 |

## 4. 有界项（不粉饰）

1. **北锚是 STEP 端点代理。** 物理面层北锚 \(x=-23.895\)、门架北锚 \(x=-44.909\) 在 STEP 外。
2. **门架索分类不完整。** `portal_rope` 227 单元。142 榀是站位对账，不是索单元数。
3. **几何垂度 214.18 m vs 227.30 m。** 过 15 m 门，不是成型线拟合。
4. **面层索总长 164 516 m**，约比四跨悬链估计长 20%。
5. **粗化中心线不连通。** 22 096 个分量。第一切线奇异。无收敛位移、无反力、无频率。
6. **四件套有文件，但没有完成增量。** 不得写成已求解。
7. **48c7f304 不是正式新主 deck。** 正式哈希是 `41fb3222`。
8. TARGET-FREQ 未打开。没有十四阶复现。

这些有界项没有被写成硬门 FAIL。硬门（坐标恒等、21/142 榀、锚分集、§7.76 词法、冻结哈希未改、禁源）闭合。

## 5. 最终判定

| 项 | 判定 | 一句依据 |
|---|---|---|
| 82548e6a 未改 | **成立** | 当场 `sha256sum` |
| 新主 deck 已交 | **成立** | `zjg_catwalk_ccx221.inp` / `41fb3222` |
| IC 为单元号+积分点+六 PK2 | **成立** | 204 208 行独立回读 |
| 不再是 ELSET+单轴 | **成立** | 新 deck 0 行 ELSET 卡 |
| 坐标过门 | **成立** | identity + K16+876 |
| 面层/门架锚分开 | **成立** | 312 ∩ 16 = ∅ |
| 21 道横通道 | **成立** | 21/21，插入 0 |
| 142 榀门架（不是槇） | **成立** | 71×2=142，单位 U+6980 |
| ccx 已对新哈希开跑 | **成立** | 2.21，exit 255，有方程数 |
| 读入 IC 成功 | **成立** | `parse_fail_ic=false` |
| 四件套文件 | **成立** | `.frd/.dat/.sta/.cvg` 均存在 |
| 已求解静力/模态 | **不成立** | 矩阵奇异，无收敛增量 |
| 十四阶复现 | **不成立** | TARGET-FREQ 未打开 |

**总评：新主 deck 过门（§7.76 PK2 + 新哈希 + 冻结 82548e6a 未改 + 21/142 榀 + 分锚）。CalculiX 2.21 读入过门。求解切线因 22 096 个不连通分量奇异，不是已求解过门，不是模态过门。论文已产出。不 push。**
