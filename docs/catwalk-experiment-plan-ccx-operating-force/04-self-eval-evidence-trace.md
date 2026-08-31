# 自评留痕（新对话：CCX 运营力实验方案）

评估人：Cursor Grok 4.6（run `bc-c6ba63ad-6f05-4985-8c74-bb0f29be249f`，https://cursor.com/agents/bc-c6ba63ad-6f05-4985-8c74-bb0f29be249f）。  
未向用户提问。未改写 `zjg_catwalk_migrate_main.inp`。未 push 到 default。未开新 PR。未 merge PR #19。  
依据只引用本仓库文件、本机命令、GitHub MCP / `gh` 对 `Hiram-test/model` 的输出。

工作目录 `/workspace`。分支 `cursor/catwalk-main-deck-gate-f23d`。计划写下时 HEAD=`0d7eaf5d79ba2daea55a7834d489001bb7fd9213`。

---

## 0. 用户原句 → 本岗验收（原句不改写）

| 用户原句 | 我当作硬验收 | 本岗判定 | 依据 |
|---|---|---|---|
| 好了 端到端开始跑了 | 本对话交出可执行预注册 + Methods 草案，对象钉死为运营力 | **成立（方案层）** | 本目录四份正文 + `locked-objects.json` |
| 产出完整论文才算结束 | 完整论文仍是总目标；本对话交付的是实验方案章，不是宣称论文已结束 | **未结束总目标；本岗方案已交** | `catwalk-fem/paper/` 仍写自制 deck 为正路，与本方案冲突，不得在本岗改成 符合 |
| 参考资料 方案 计划 计算 全部是 Grok Build 和虚拟机 | 不引用用户口头补数；哈希与命令当场算 | **成立** | 下方命令块 |
| cat那个 目标是完整复现附件2-3的力学计算指标 但是论文写的是从零开始全自动跑完流程 仓库里有19个skill | 论文叙事=19 skill 从零自动；对照对象先运营力，不是十四频 | **成立（定位）** | `bridge-fem-skill-suite/SKILL_INDEX.md` 19 行；`isolated/TARGET-FREQ.json` 隔离 |
| 进行文献调研 mdpi的标准和模版 | Methods 按 MDPI *Applied Sciences* IMRAD；披露 GenAI | **成立** | https://www.mdpi.com/journal/applsci/instructions ；草案 `02-…` |
| 定位是一篇agentic fea 但是对于悬索桥猫道 从图纸翻模 索力迭代 静力计算 计算工况 全自动 | 章程写猫道 + 翻模/索力/静力/工况 | **成立（定位）** | `01` §2、`02` §2.1–2.5 |
| intro写难点 技术上 对象上（猫道） | Methods/Intro 分技术难点与猫道对象难点 | **成立（草案已写）** | `02` §2.1 |
| grok build写方案新对话执行 | 本对话只写方案，不改主 deck | **成立** | `git diff` 不得出现 `zjg_catwalk_migrate_main.inp` |
| 然后每一章机会对应的skill设计和流程设计 | 每小节 Skill + Process | **成立** | `02` 各节末 |
| 不过的自己评估 一定要跑通产出论文。不允许找我。让gork自己评估 但是要写依据 留痕 | 自评估、留命令、不提问 | **成立** | 本文 |
| 只迁 ANSYS，对照看，先静力、索力平衡、预应力。别把自制 deck 写成正路 | 正路=974211b2；自制四哈希冻结 | **成立** | 本岗未把 760c0ee4 写成正路 |
| 预应力在mct也有 | `*INIFORCE` 1123 | **成立** | sidecar + 正文 scrape |
| 从零复现是第一步 | 从 `.mct` 体迁出，不用归档 CSV 当新主 | **成立** | `mct-from-zero/README.md`；`used_archive_csv_as_new_main=false` |
| 报结论，错误结论也可以。不报停了/没有/没进账本。你有一个主要的模型，主体，这个东西是一直要往前推的，不能把它改坏了乱改 | 必须报：`.dat` Umax \(9.26\times 10^{9}\) mm 机构型；FRD 首块 DISP 0 个原 NSET 不是第二条位移结论；S≈IC 最差 −19.1% 不是索力平衡；703.46 不当 Results；不写 符合。主模型字节不动 | **成立** | §1–§4 |

---

## 1. 当场命令（本岗复算）

```
$ git rev-parse --abbrev-ref HEAD
cursor/catwalk-main-deck-gate-f23d

$ git rev-parse HEAD
0d7eaf5d79ba2daea55a7834d489001bb7fd9213

$ sha256sum catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp \
            catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp
974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1  catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp
974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1  catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp

$ cmp catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp \
      catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp ; echo $?
0

$ sha256sum "catwalk-fem/mct-from-zero/source/01_设计资料与规范/猫道 - 门架索合建模型2.mct"
0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1

$ sha256sum catwalk-fem/artifacts/zjg_catwalk_coarsened.inp \
            catwalk-fem/artifacts/zjg_catwalk_ccx221.inp \
            catwalk-fem/artifacts/zjg_catwalk_main.inp \
            catwalk-fem/artifacts/zjg_catwalk_cleared.inp
82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da  …/zjg_catwalk_coarsened.inp
41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a  …/zjg_catwalk_ccx221.inp
c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84  …/zjg_catwalk_main.inp
760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9  …/zjg_catwalk_cleared.inp

$ ls catwalk-fem/eval/ccx_mct_from_zero/
ccx_run.json

$ sha256sum catwalk-fem/eval/ccx_mct_from_zero/ccx_run.json
7e43993e42729e6f5b5b90ca1633b985177a8661dd81429874d073996f7d0733

$ git show --name-only --oneline 16e2d22
16e2d22 Record first ccx 2.21 static on the MCT-migrated deck.
catwalk-fem/eval/ccx_mct_from_zero/ccx_run.json
catwalk-fem/mct-from-zero/artifacts/mct_from_zero_inp_meta.json
catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp
catwalk-fem/mct-from-zero/emit_ccx.py
# 无 .frd .dat .sta .cvg
```

独立计数（本岗 Python，读 `974211b2` 正文）：节点 1125 个不重复；T3D2 1123；B31 71；IC 八字段行 8984；\(X_{\max}-X_{\min}=4270609\) mm。  
eid 1 首行 IC PK2 迹 \(285.3700+0+418.0905=703.4605\) N/mm²。  
\(F/A=15686250/22298.69164950066=703.4605548416231\) N/mm²。  
**结论：703.46 是源侧输入预应力（IC 迹 = MCT INI-EFORCE mean / A），不是 974211b2 求解运营力。禁止当 Results。**

`rg 6712e918`：工作树无命中。  
`rg 703.46`（排除 `.inp`）：工作树无命中——该数只作为本方案的**排除项**写入 docs，不作为已有结果账。

---

## 2. 必须上报的结论（含错误结论；不写「停了 / 没有 / 没进账本」）

### 2.1 科学 / 计算结论

1. **P0 位移权威是 `.dat`：** \(U_{\max}=9.26\times 10^{9}\) mm，1125 个原节点 U。分类 **机构型**。这是计算结论，不是 符合。  
2. **`.frd` 第一块 DISP 含 0 个原 NSET 节点，不是第二条位移结论。** T3D2 被扩成 C3D8I，原 NSET 不在 FRD 网格上。不得用它再报一个 Umax。  
3. **S≈IC 不是索力平衡。** 最差相对误差 **−19.1%**。不得把应力贴近初应力写成平衡。  
4. **eid 1** \(15\,687\,915\) N vs sidecar MCT \(15\,686\,250\) N 仍锁为计算对；不是运营力表检验。  
5. **703.46 不得当结果。** 它是 IC 迹 / \(F/A\)。  
6. **不写 符合。** H-ZJG-CCX-OF-001 尚未被检验。  
7. **自制 deck 不是正路。** 四哈希仍在；`6712e918` 不换主。

### 2.2 账本 / 证据结论（有主模型；缺的是行和四件套）

6. **主模型在分支上，哈希是 974211b2。** 路径 `catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp`，与 `mct_from_zero_static.ccx.inp` 字节相同。  
7. **`HASH_LEDGER.json` 仍把 `new_main` 写成 760c0ee4；`checksums.sha256` 无 migrate 行。** 这是账本行滞后，不是「没有主模型」。本岗不改 `.inp` 去迁就旧账本。  
8. **P0 四件套（`.frd/.dat/.sta/.cvg`）未进 `16e2d22`。** 结论：求解曾被写成 JSON，原始结果未进账本。Go/No-Go 在四件套上 = No-Go。  
9. **GitHub Actions 有跑，但全是扎青预应力工作流，0 秒 failure。** 例：`32868201652`。结论：Actions 节点对猫道运营力 = 错对象，不是「没跑过 CI」。  
10. **张靖皋猫道 DWG 不在工作树。** 结论：叠合走「图纸缺省 → 全量 MCT scrape」。扎青 DWG 在 `source-inputs/`，对象错，不用。  
11. **运营力表 CSV 只在归档索引里。** `mct_case_1..6_element_force.csv` 有哈希，无正文。结论：对照表未进本树；禁止手填。  
12. **现有论文 `zjg_catwalk_agentic_fea.md` 仍把 760c0ee4 写成新主、不交计算。** 结论：论文正本与锁定主模型不一致。本岗不把自制路径改回正路；也不在本对话改主 deck。

### 2.3 流程结论

13. **19 个 skill 的设计已映射到 Methods 各节；A0 的 G6/G12/G13/G15 ledger 不存在。** 结论：流程设计已写；端到端 gate 未过。  
14. **PR #19 `merged=false`，`draft=true`，head=`0d7eaf5`。** 本岗不合并。  
15. **VM / agent 跑通 ≠ 科学复现。**

---

## 3. 本岗做了 / 没做

| 项 | 做了？ | 依据 |
|---|---|---|
| 写预注册 | 是 | `01-preregistration.md` |
| 写 MDPI Methods 草案（英文） | 是 | `02-mdpi-experiment-setup-draft.md` |
| 写 claim-trace | 是 | `03-claim-to-artifact-trace.md` |
| 锁 974211b2：`.dat` 机构型 Umax、FRD 首 DISP 非第二条、S≈IC 非平衡 | 是 | `locked-objects.json` |
| 明确排除 703.46 作 Results | 是 | `01` §1、§8；`02` §2.4；本文 §1 |
| 改主 deck | **否** | 不得出现在 diff |
| 把自制 deck 写成正路 | **否** | 正路句只指向 974211b2 |
| 发明新的求解器数字 | **否** | 只用锁定三事实 + 已有 sidecar 路径声明 |
| 开新 PR / merge / push default | **否** | 任务硬约束 |
| 问用户 | **否** | 本文件 |

---

## 4. Go / No-Go（写在对象里，不写在聊天里）

| 对象 | Go/No-Go | 一句依据 |
|---|---|---|
| 主 `.inp` 974211b2 | **Go** | 当场 `sha256sum` |
| P0 `.frd` 第一块 DISP | **不是位移结论** | 0 个原 NSET 节点；T3D2→C3D8I |
| P0 `.dat` 原节点 U | **权威 / 机构型** | \(U_{\max}=9.26\times 10^{9}\) mm，1125 点 |
| P0 `.sta` | **No-Go** | 同上 |
| P0 `.cvg` | **No-Go** | 同上 |
| 运营力表 M2 | **No-Go** | 归档 CSV 无正文；INI-EFORCE 不是 M2 |
| Actions（猫道 ccx） | **No-Go** | 现有 run 是 zhaqing-prestress |
| 科学 符合 | **禁止写** | `.dat` 机构型 \(9.26\times 10^{9}\) mm；S≈IC 最差 −19.1%；M2 错类型 |
| 方案交付（本对话） | **Go** | docs 四件 + locked JSON |

---

## 5. 总评

**主模型是 974211b2，还在，没改坏。**  
位移权威：`.dat` \(U_{\max}=9.26\times 10^{9}\) mm（1125 原节点 U），**机构型**。  
FRD 首块 DISP（0 原 NSET）**不是**第二条位移结论。  
S≈IC 最差 −19.1% **不是**索力平衡。  
703.46 排除出 Results。**不写 符合。**  
账本 JSON 仍写 760c0ee4；migrate 文件已在分支。本单只改 `docs/catwalk-experiment-plan-ccx-operating-force/`。
