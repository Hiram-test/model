# Grok 自评留痕（catwalk-main-deck-gate-f23d，论文收口）

评估人：本 run 的模型（Cursor Grok 4.6）。未向用户提问。  
依据只引用本仓库文件、Release 哈希、本机命令输出和 CalculiX 2.21 手册 §7.76。  
门架计数单位：**榀（U+6980）**，不是槬（U+69EC）。

## 1. 任务理解（先写依据）

| 用户句 | 我当作硬验收 | 依据 |
|---|---|---|
| 产出完整论文才算结束 | `paper/*.md` + 可编译 `paper/*.tex` + PDF；十章结构按 `PLAN.md` §4 | 用户原文；`PLAN.md` §4、§6 |
| 自己评估、写依据、留痕 | 本文件 + 命令输出 + JSON | 用户原文 |
| 不允许找用户 | 全程不提问 | 用户原文 |
| \(x=\)桩号\(-K16+876\) | 节点/边界/荷载同一公约；禁止 `X-xmin` | SKILL 硬约束 1–2 |
| 面层锚和门架锚分开 | `N_FLOOR_*` 与 `N_PORTAL_*` 分 NSET、分 `*BOUNDARY`，交集为空 | 用户原文；theory v1.2 §4 |
| 21 道横通道 | 对账 21 个图纸站，缺站记账 | theory v1.2 表；`PASSAGE_X` 长度 21 |
| 142 榀门架（不是槬） | 71×2=142，单位写榀 | 用户更正；theory v1.2 §2.6 |
| 已给路径 / PR #19 / 分支 | 只在 `cursor/catwalk-main-deck-gate-f23d` 上收口 | 用户原文 |
| `zjg_catwalk_coarsened.inp` SHA-256 `82548e6a…276ab6da` | 重算必须一致 | 用户原文 |
| `write_inp.py` | 作为该哈希的写入器；本 run 不改出发射格式 | 用户原文 |
| 猫道计算已给：ccx 已对 82548e6a 跑过 | 记录并在本机复现，不改哈希 | 用户原文 |
| 读入 `*INITIAL CONDITIONS` 失败（`E_FLOOR_ROPE,3.549611E+08`，exit 201） | stdout 必须出现该行 | 用户原文；本机复现 |
| 无 .frd，.dat 空，.sta/.cvg 只有表头 | 副本产物核对 | 用户原文；`/tmp/ccx-82548e6a/` |
| 墙钟 <1 s，无方程数 | 本机 0.74–0.82 s；无 assembled equation count | 用户原文；本机 `time` |
| 这份 deck 的 TYPE=STRESS 是 ELSET+单轴 | 词法审计两行 | 冻结 `.inp` 90863–90865 |
| ccx 2.21 要单元号+积分点+六应力 | 手册 §7.76 | `ccx_2.21.pdf`；`ccx -v` = 2.21 |
| 不改 82548e6a | 运行前后 `sha256sum` 相同 | 用户原文 |

## 2. 本 run 实际做了什么

1. 核分支 `cursor/catwalk-main-deck-gate-f23d`，当场重算 INP 哈希 = `82548e6a…276ab6da`。
2. 只读审计 `pipeline/audit_frozen_deck.py`：初应力词法、21/142、分锚；**不写回** `.inp`。
3. 安装并运行 `calculix-ccx` 2.21，只在 `/tmp/ccx-82548e6a/` 的副本上求解。
4. 复现 exit 201 与已给卡图；日志拷入 `artifacts/ccx_82548e6a.*`。
5. 写出完整中文论文 `paper/zjg_catwalk_agentic_fea.md`（十章 + 附录 142 榀全表）。
6. 写出完整英文 TeX 并 `pdflatex` 两遍，得到 11 页 PDF（exit 0）。
7. 单元测试四处全部通过。未改 `write_inp.py` 的发射格式，未改冻结 `.inp`。

## 3. 过门证据（可复核命令）

### 3.1 冻结哈希（运行前后）

```
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  catwalk-fem/artifacts/zjg_catwalk_coarsened.inp
```

`audit_frozen_deck.py` 打印：`hash_unchanged: true`。  
`original_hash_before == original_hash_after == FROZEN_SHA256`。

### 3.2 单元测试

```
test_coord_gate ok
test_write_inp ok
test_reconcile ok
test_audit_frozen_deck ok
```

### 3.3 142 榀门架（不是槬）

来自 `portal_142_ledger.json` / `audit_frozen_deck.py`：

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
not_unit              槬
pass_142              true
```

逐站表：`artifacts/portal_142_table.md`（71 行全 `ok=Y`）。

### 3.4 面层/门架锚分开

从冻结 `.inp` 回读：

```
N_FLOOR_ANCHOR  312
N_PORTAL_ANCHOR 16
overlap         0
*BOUNDARY cards N_FLOOR_ANCHOR / N_PORTAL_ANCHOR / N_SUPPORT_SADDLE_ENDS
south floor x_mean  4209.985
south portal x_mean 4221.093
```

### 3.5 21 道横通道

`topology_reconcile.json`：21/21，插入 0，检测器 `element_dy_or_node_yspan`。

### 3.6 初应力词法

冻结 deck 第 90863–90865 行：

```
*INITIAL CONDITIONS, TYPE=STRESS
E_FLOOR_ROPE, 3.549611e+08
E_PORTAL_ROPE, 2.426295e+08
```

`ic_format_audit.json`：`elset_plus_uniaxial=true`，`ccx_2_21_legal=false`。  
写入器格式化串 `3.549611e+08` 与 `initial_state()["sigma_floor_Pa"]` 的 `:.6e` 一致。

### 3.7 CalculiX 2.21 本机复现

```
$ ccx -v
This is Version 2.21

$ python3 catwalk-fem/pipeline/audit_frozen_deck.py
{
  "hash_unchanged": true,
  "ic_elset_uniaxial": true,
  "portals_142_pass": true,
  "ccx_exit": 201,
  "ccx_wall_s": 0.7376800000000117
}
```

先前一次副本运行墙钟 0.815 s。两次都 <1 s。

stdout 致命行（`artifacts/ccx_82548e6a.stdout.txt`）：

```
 *ERROR reading *INITIAL CONDITIONS. Card image:
        E_FLOOR_ROPE,3.549611E+08
 *ERROR in calinput: at least one fatal
        error message while reading the
        input deck: CalculiX stops.
```

产物核验（`/tmp/ccx-82548e6a/`，已拷贝到 artifacts）：

| 文件 | 结果 |
|---|---|
| `job.frd` | 不存在 |
| `job.dat` | 0 字节 |
| `job.sta` | 仅 `SUMMARY OF JOB INFORMATION` 表头 |
| `job.cvg` | 仅收敛表头 |
| equation count | 无（横幅 “number of:” 标明 estimated upper bounds，不是组装方程数） |

与已给计算逐项对齐。

### 3.8 论文

| 文件 | 结果 |
|---|---|
| `paper/zjg_catwalk_agentic_fea.md` | 中文十章 + 附录 A 142 榀全表 + 附录 B ccx 摘录 |
| `paper/zjg_catwalk_agentic_fea.tex` | 英文十章，`pdflatex` 两遍 exit 0 |
| `paper/zjg_catwalk_agentic_fea.pdf` | 11 页，275 851 字节，无 LaTeX Error |

正文不含 `255.56`、不含 `0.0296` 作为求解输入。TARGET-FREQ 未打开。

## 4. 有界项（不粉饰）

1. **北锚是 STEP 端点代理。** 物理面层北锚 \(x=-23.895\)、门架北锚 \(x=-44.909\) 在 STEP 外。代理在 \(x=0\) 与 \(x\approx46\)。未造负 \(x\) 节点。
2. **门架索分类不完整。** 粗化后 `portal_rope` 227 个单元；南门架锚取自 \(x=4221.093\) 的 `portal_or_beam`（距 4225.700 为 4.61 m）。142 榀是门架站位对账，不是门架索单元数。
3. **几何垂度 214.18 m vs 227.30 m**（差 13.12 m）。过 15 m 门，不是成型线拟合。
4. **高程直方图峰在 700 / 3023**，不是鞍点。过门依据是鞍点邻域 \(Z_{p90}\)。
5. **面层索总长 164 516 m**，约 5141 m/根，比四跨悬链估计偏长约 20%。
6. **初应力卡对 ccx 2.21 不合法。** 求解器未组装。无位移、反力、频率。
7. **ccx 读入横幅里的 nodes: 1 689 014 是 estimated upper bounds**，不得写成方程数。已给「无方程数」成立。

这些有界项没有被写成硬门 FAIL。硬门（坐标恒等、21/142 榀、锚分集、完整关键字、冻结哈希、禁源、已记录的 IC 失败）都闭合。它们必须留在论文和本评估里。

## 5. 最终判定

| 项 | 判定 | 一句依据 |
|---|---|---|
| 可回读主 deck | **成立** | 7.7 MB，关键字齐全 |
| 带哈希且未改 | **成立** | 当场 `sha256sum` = `82548e6a…276ab6da` |
| 坐标过门 | **成立** | identity + 鞍点 \(Z\)；未减 xmin |
| 面层/门架锚分开 | **成立** | 两 NSET 交集空，南 \(x\) 差 11.1 m |
| 21 道横通道 | **成立** | Y 跨度 21/21，插入 0 |
| 142 榀门架（不是槬） | **成立** | 71×2=142，插入 0，单位 U+6980 |
| ccx 已跑 | **成立** | 已给 + 本机 2.21 复现 exit 201 |
| IC 失败行 | **成立** | `E_FLOOR_ROPE,3.549611E+08` |
| 无 .frd / 空 .dat / 表头 .sta.cvg | **成立** | `/tmp/ccx-82548e6a/` 与 artifacts 拷贝 |
| 墙钟 <1 s | **成立** | 0.74–0.82 s |
| 无方程数 | **成立** | 无 assembled equation 行 |
| 论文 | **成立** | 中文十章 + TeX PDF 11 页 |
| 已求解静力/模态 | **不成立** | 读入阶段失败 |
| 十四阶复现 | **不成立** | TARGET-FREQ 未打开，也无振型 |

**总评：主 deck 过门 + 142 榀对账过门 + CalculiX 2.21 初应力词法失败过门（已记录）。不是求解过门，不是模态过门。论文已产出。冻结哈希未改。**
