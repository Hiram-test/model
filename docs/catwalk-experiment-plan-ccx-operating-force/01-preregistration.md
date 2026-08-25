# 预注册：张靖皋猫道 CalculiX 运营力对照（H-ZJG-CCX-OF-001）

<!--
用户原句（不得改写目标）：
- 好了 端到端开始跑了
- 产出完整论文才算结束
- 参考资料 方案 计划 计算 全部是 Grok Build 和虚拟机
- cat那个 目标是完整复现附件2-3的力学计算指标 但是论文写的是从零开始全自动跑完流程 仓库里有19个skill
- 进行文献调研 mdpi的标准和模版
- 定位是一篇agentic fea 但是对于悬索桥猫道 从图纸翻模 索力迭代 静力计算 计算工况 全自动
- intro写难点 技术上 对象上（猫道）
- grok build写方案新对话执行
- 然后每一章机会对应的skill设计和流程设计
- 不过的自己评估 一定要跑通产出论文。不允许找我。让gork自己评估 但是要写依据 留痕
- 只迁 ANSYS，对照看，先静力、索力平衡、预应力。别把自制 deck 写成正路
- 预应力在mct也有
- 从零复现是第一步
- 报结论，错误结论也可以。不报停了/没有/没进账本。你有一个主要的模型，主体，这个东西是一直要往前推的，不能把它改坏了乱改

对照对象是 CCX 运营力，不是 MCT-vs-ANSYS 源侧预应力 703.46。
主模型不得改写：zjg_catwalk_migrate_main.inp / 974211b2。
自制失败现场 82548e6a / 41fb3222 / c635dad7 / 760c0ee4 冻结，不得写成正路。
-->

**Registry title.** Agentic FEA of a suspension-bridge construction catwalk: preregistered comparison of CalculiX operating force against a same-source MIDAS/ANSYS operating-force table.

**Hypothesis ID.** `H-ZJG-CCX-OF-001`

**Date frozen.** 2026-08-25 (this plan). Branch `cursor/catwalk-main-deck-gate-f23d`. PR https://github.com/Hiram-test/model/pull/19 (`merged=false`). Head at plan write: `0d7eaf5d79ba2daea55a7834d489001bb7fd9213`. Evaluator run `bc-c6ba63ad-6f05-4985-8c74-bb0f29be249f`.

**Journal target.** MDPI *Applied Sciences* research Article (IMRAD). Methods must be reproducible; software versions, code availability, and a preregistration identifier are required; generative-AI use in design or analysis must be disclosed in Methods ([Instructions for Authors](https://www.mdpi.com/journal/applsci/instructions)).

**This document is a plan, not a scientific success claim.** A finished VM job is not a physics claim. The word 符合 is forbidden unless a DISP-bearing hashed `.frd/.dat/.sta/.cvg` set exists and the operating-force table comparison is executed against that set.

---

## 1. Exact claim under test

**Claim H-ZJG-CCX-OF-001.**  
On the locked MCT-migrated CalculiX deck `974211b2`, after a static solve whose raw result files contain nodal DISP, the **element axial operating force** (运营力) of each cable `eid` recovered from those result files agrees with the **same-source MCT or ANSYS operating-force table** for the matching load case, inside the pre-registered tolerance of §7. The primary unit is newton per cable element. Displacement extrema (`Umax`) and the presence/absence of DISP are co-primary metrics, not optional diagnostics.

**The claim is not:**

- MCT TENSTR/truss input \(\sigma = 703.46055\,\mathrm{N/mm}^2\) versus ANSYS `INISTATE` \(703.46280\,\mathrm{N/mm}^2\) (relative \(3.19\times 10^{-6}\)). That pair is **source-to-source prestress**. It is not a `974211b2` solve. It is **forbidden as a paper results conclusion**.
- Agreement of CalculiX `*INITIAL CONDITIONS, TYPE=STRESS` with MCT `*INIFORCE` / `*INI-EFORCE`. Those cards are **inputs**. This-turn reread of the hashed deck shows the PK2 trace on eid 1 equals \(703.4605\,\mathrm{N/mm}^2\), which is exactly \(F/A\) of MCT INI-EFORCE mean \(15\,686\,250\,\mathrm{N}\) over section 1 area \(22\,298.69164950066\,\mathrm{mm}^2\). That identity is bookkeeping of the migrate, not operating force.
- Agreement with 附件2-3 fourteen frequencies. Those values live in `catwalk-fem/isolated/TARGET-FREQ.json` and must not enter the solver deck.
- “The homemade STEP decks now solve.” Frozen scenes `82548e6a`, `41fb3222`, `c635dad7`, `760c0ee4` are **not** the main path. Trial `6712e918` died at SPOOLES, is absent from this tree, and must not be swapped in.

**Locked compute conclusions on `974211b2` (may be physically bad; still written; not 符合):**

| Fact | Locked value | Status |
|---|---|---|
| CalculiX exit | 0 | locked compute conclusion |
| \(U_{\max}\) | \(9.264\times 10^{9}\) mm | locked compute conclusion; **likely failed static** |
| eid 1 axial | \(15\,687\,915\) N (CCX) vs \(15\,686\,250\) N (MCT number recorded in the sidecar) | locked compute conclusion; **not** a declaration that the operating-force table was used |

These three numbers are the only solver results this plan is allowed to treat as compute conclusions. Additional floats inside `catwalk-fem/eval/ccx_mct_from_zero/ccx_run.json` are sidecar text. They are not independently re-derived from hashed `.frd/.dat/.sta/.cvg`, because those four files are **not in the working tree** (commit `16e2d22` recorded only the JSON).

---

## 2. Object, main model, and sources

### 2.1 Object

Zhangjinggao (张靖皋) suspension-bridge **construction catwalk**, portal-and-cable combined model. Paper positioning: **agentic FEA** — drawings-or-MCT scrape → geometry overlay → cable-force / initial-state iteration → static solve → load cases — executed by the 19-node `bridge-fem-skill-suite` plus `catwalk-fem` executor, without a human in the loop.

Solver of record for this study: **CalculiX 2.21** only. ANSYS and MIDAS Civil NX are **controls**, not the execution engine. Do not clone other repositories. Do not touch `demo-rl-calculix`.

### 2.2 Locked main model (do not swap, do not edit)

| Field | Value |
|---|---|
| Path | `catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp` |
| SHA-256 | `974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1` |
| Bytes | 930300 |
| Byte-identical copy | `catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp` (`cmp` identical this turn) |
| Nodes / elements | 1125 nodes; 1123 `T3D2` (MCT `TENSTR`); 71 `B31` (MCT `TRUSS` 门架) |
| Coordinates | MCT millimetres; \(X\in[831091,\,5101700]\); span \(4270.609\) m |
| IC | 8984 = \(1123\times 8\) eid+IP+six global PK2 (`ccx` 2.21 §7.76) |
| First commit of migrate copy on `#19` | `0d7eaf5d79ba2daea55a7834d489001bb7fd9213` |
| First commit that recorded a static JSON | `16e2d222d3e7dc1b503d528d2dea621f1bcbcffa` |

**Ledger conclusion (must be reported, not “stopped / missing”):** `artifacts/HASH_LEDGER.json` still lists `760c0ee4` as `new_main`. `artifacts/checksums.sha256` has no `zjg_catwalk_migrate_main.inp` line. The file **is** on the `#19` branch and hashes to `974211b2`. This plan treats `974211b2` as the main model by the locked-path rule. It does **not** rewrite the deck to “fix” the ledger. A later turn may add a ledger **line** without touching the `.inp` bytes.

### 2.3 Hashed sources (not this-study CCX results)

| Source | SHA-256 | Role |
|---|---|---|
| Archive MCT `01_设计资料与规范/猫道 - 门架索合建模型2.mct` (repo copy under `catwalk-fem/mct-from-zero/source/`) | `0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1` | From-zero scrape. `*INIFORCE` 1123 TENSTR. Prestress lives here. |
| Release `catwalk-attachment23-v2.0-s10-20260716` `cw_S10_0716t050342_a4_eq.db` | `17e0bac8717e7c32a407571d33e38dd777736b31b6656684e53449fa8c9d40fd` | ANSYS control. ASCII/MAPDL extract in this tree: **no** `INISTATE` table. Do not invent one. |
| STEP centreline (coordinates only; not the main deck) | `d03d01e38b823df5af4c1ff9b0b175fdfb87b097b9cda9a03af5d14e9c763344` | Dual-walkway millimetre STEP. Different mesh from MCT \(Y\approx 0\). Not 1:1. |

MCT `*STLDCASE` names read this turn from the GB18030 body (not invented):

1. 自重 (CS)  
2. 二期 (CS)  
3. 整体降温15 (T)  
4. 整体降温34 (T)  
5. 施工风荷载 (WL)  
6. 最大阵风 (W)  
7. 施工荷载 (L)

Stage `一次成桥` activates groups 二期 + 自重. Combinations in `*LOADCOMB` include 工况1恒载, 工况2 恒+施工, 工可3恒+施工+温度, 工可4恒+施工+施工风, 工况5恒+最大阵风, 工况6恒+施工+温34. Those six names are the **intended operating-force cases**. Their element-force CSV bodies live in archive `03_猫道动力分析/MCT基准复现_V1.0/` (index only in this tree). The CSV files are **not** the new main and **not** present as bytes here. They must be fetched by hash from the archive or rebuilt by solving MCT; they must not be hand-typed.

---

## 3. Same-source geometry overlay protocol

**Rule.** Overlay must be same-source. Use drawings if present. If drawings are absent, scrape MCT fully, then overlay.

**This-turn drawing gate.**

| Candidate | Present in this working tree? | Allowed as ZJG catwalk drawing? |
|---|---|---|
| Zhangjinggao catwalk DWG/DXF | **No** | — |
| `source-inputs/zhaqing-suspension-bridge/drawings/*.dwg` | Yes | **No.** Wrong bridge (扎青). |
| `catwalk-theory/thirteen-mode-models/*.pdf` | Yes | **No.** Theory package, not construction drawings. |
| MCT body `0d18e3f7…` | Yes | **Yes, as scrape source** because drawings are absent. |
| S10 STEP `d03d01e3…` | Cited by hash; 77 MB body not stored in git | Overlay only after an explicit same-source decision. Mesh is not 1:1 with MCT. |

**Protocol (N02–N07, gate G6 `geometry_overlay_report`):**

1. **Drawing probe (G1–G3).** Search the run inputs and the Zhangjinggao archive manifest for catwalk DWG/PDF sheets whose title block names 猫道 / 门架 / 承重索. If any hashed drawing exists, extract stations, cable areas, and anchor chainages from the drawing, then overlay MCT nodes onto those stations.  
2. **Absent-drawing branch (active now).** Scrape the full MCT: `*NODE`, `*ELEMENT`, `*GROUP`, `*CONSTRAINT`, `*SECTION`, `*MATERIAL`, `*STLDCASE`, `*INIFORCE`, `*INI-EFORCE`. Do not use archive CSV as the geometry source.  
3. **Overlay.** Compare every MCT node \((X,Y,Z)\) to the nodes written into `974211b2`. Pass only if 1125/1125 coordinates match to the printed precision of the `.inp` and the span remains \(4270.609\) m.  
4. **Forbidden overlays.** Homemade STEP decks (`82548e6a` family) onto MCT; 扎青 DWG onto 张靖皋; S10 73 692 LINK180 onto MCT 1 194 elements as a 1:1 map; any \(X-x_{\min}\) shift that the MCT body does not contain.  
5. **Record.** `geometry_overlay_report.json` must name the source hash, the probe outcome (`drawings_absent` | `drawings_used`), and the 1125-row residual table hash. Bot chat is not a node.

---

## 4. Arms / baselines

| Arm ID | Deck | Role | May become main? |
|---|---|---|---|
| **A0** | `974211b2` MCT→CCX migrate | **Main.** Linear static P0 already run. Operating-force cases P1–P6 planned on copies that do not change A0 bytes. | It already is. |
| B-MCT | Hashed `.mct` `0d18e3f7` | Control table source (operating force after MCT solve, or hashed archive case CSV once fetched). | No |
| B-ANSYS | Hashed `.db` `17e0bac8` | Control only if a real POST1/INISTATE/operating-force extract appears. Current extract: **blocked**. | No |
| F1 | `82548e6a` | Frozen ELSET+uniaxial fail site | No |
| F2 | `41fb3222` | Frozen IC-pass / first-increment singular site | No |
| F3 | `c635dad7` | Frozen 4 unconstrained B31 site | No |
| F4 | `760c0ee4` | Frozen cleared homemade; not a calculation main | No |
| T-dead | `6712e918` | Trial homemade; SPOOLES death; absent | No |
| X-demo | `demo-rl-calculix` | Out of scope | No |

A0 load step currently on the locked deck: `*STATIC` with `*DLOAD` GRAV + `*CLOAD` 二期, IC from MCT INI-EFORCE mean. That is **P0** (IC + 自重 + 二期). It is the first from-zero static, not the full operating-force matrix.

---

## 5. Cases

| Case ID | MCT name | CCX action on A0 | Status at plan freeze |
|---|---|---|---|
| **P0** | 一次成桥 ≈ 自重 + 二期 + IC | Already executed (JSON sidecar). Lock exit 0, \(U_{\max}=9.264\times 10^{9}\) mm, eid1 \(15\,687\,915\) N vs \(15\,686\,250\) N. | **Compute conclusions locked.** Scientific 符合: **No-Go.** Raw four-file set: **missing**. |
| P1 | 工况1恒载 | Re-request FORC/S + U; write a **new** job directory; do not edit `974211b2`. | Planned |
| P2 | 工况2 恒+施工 | Add 施工荷载 `*CLOAD` from MCT scrape. | Planned |
| P3 | 工可3恒+施工+温度 | Add 整体降温15. | Planned |
| P4 | 工可4恒+施工+施工风 | Add 施工风荷载. | Planned |
| P5 | 工况5恒+最大阵风 | Add 最大阵风. | Planned |
| P6 | 工况6恒+施工+温34 | Add 整体降温34. | Planned |

P1–P6 decks, if emitted, must be **new paths** with new hashes. The main file `zjg_catwalk_migrate_main.inp` stays `974211b2`. Temperature and wind cards must come from the MCT body, not from memory.

P0 already fails the displacement sanity gate in §7. That failure is a **written conclusion**, not a reason to stop reporting or to swap the main model.

---

## 6. Primary metrics

Pre-registered. Substitution after seeing numbers is a protocol violation.

| ID | Metric | Definition | Source files that count |
|---|---|---|---|
| M1 | \(F_{\mathrm{ccx}}(eid)\) | Axial operating force (N) of each of 1123 cables after the step | Hashed `.dat` and/or `.frd` element field, with the recovery formula written in `solver_run_record.json` |
| M2 | \(F_{\mathrm{table}}(eid)\) | Same eid, same case, MCT or ANSYS **operating-force table** (N) | Hashed table whose provenance is “post-solve element force”, **not** `*INIFORCE` / `*INI-EFORCE` / IC PK2 |
| M3 | \(\delta(eid)=\lvert F_{\mathrm{ccx}}-F_{\mathrm{table}}\rvert/\lvert F_{\mathrm{table}}\rvert\) | Relative force error | Derived from M1, M2 |
| M4 | \(U_{\max}\) | \(\max_n \lVert \mathbf{u}_n\rVert\) (mm) | Hashed `.frd` DISP (or `.dat` U) |
| M5 | DISP presence | Boolean: `.frd` contains a DISP block with 1125 nodes | Hashed `.frd` |
| M6 | Run completeness | `.inp/.frd/.dat/.sta/.cvg` all present, SHA-256 recorded, commit recorded, Actions run recorded | Manifest |

P0 locked M4 \(=9.264\times 10^{9}\) mm and M1(eid 1) \(=15\,687\,915\) N. M2 for P0 as recorded in the sidecar is MCT **INI-EFORCE mean**, which **is not** M2 as defined here. Therefore P0 does **not** yet test H-ZJG-CCX-OF-001. That is a conclusion, not a blank.

---

## 7. Pre-registered pass / fail (scientific)

A case is **scientific PASS** only if **all** of the following hold.

1. M5 is true (DISP present, 1125 nodes).  
2. `.sta` shows a completed increment; `.cvg` exists; CalculiX exit 0 is **necessary but not sufficient**.  
3. M4 \(\le 500\) mm (catwalk live displacement scale; \(9.264\times 10^{9}\) mm fails immediately).  
4. M2 is an operating-force table, not INIFORCE / IC / 703.46.  
5. M3: median \(\le 0.01\) and 95th percentile \(\le 0.05\) over the 1123 cables.  
6. All six evidence objects of §10 exist and hash-close.

A case is **scientific FAIL** if any of 1–6 fails. **P0 is scientific FAIL** on items 2 (four-file set missing), 3 (\(U_{\max}\) huge), and 4 (sidecar compared INI-EFORCE). P0 is still a **compute conclusion**: exit 0, huge \(U_{\max}\), eid1 pair as locked.

A case is **BLOCKED** if M2 cannot be obtained without invention (ANSYS extract still empty; archive CSV not fetched). Blocked \(\neq\) “stopped / none”. Report BLOCKED with the hash of the failed extract.

---

## 8. Forbidden post-hoc substitutes

The following may not be used, after seeing data, as a success stand-in for H-ZJG-CCX-OF-001.

1. **Source-side 703.46.** MCT/CCX IC \(\sigma\) versus ANSYS `INISTATE` 703.46280. Rel. \(3.19\times 10^{-6}\) is not a results table.  
2. IC PK2 trace, `*INIFORCE`, or `*INI-EFORCE` labelled as 运营力.  
3. Promoting homemade `82548e6a` / `41fb3222` / `c635dad7` / `760c0ee4` / `6712e918` to main.  
4. `demo-rl-calculix` numbers.  
5. TARGET-FREQ / 附件2-3 spectrum match.  
6. CalculiX exit 0, or “VM ran”, or “agent finished”, as 符合.  
7. Bot chat, PR comment, or self-eval prose as a solver artifact.  
8. Archive `mct_case_*_element_force.csv` as a **new main deck**. (Allowed later as a **control table** only after the bytes are fetched and hash-checked against `archive_index_MCT基准复现_V1.0.json`.)  
9. 扎青 drawings as 张靖皋 geometry.  
10. Changing `974211b2` bytes to make \(U_{\max}\) look small.  
11. Picking a different eid, a different percentile, or a stress-only metric because force/DISP failed.  
12. Zhaqing GitHub Actions (`zhaqing-prestress-*.yml`) as evidence that the catwalk deck solved.

---

## 9. Cost budget buckets

| Bucket | What it pays for | Cap | Stop if exceeded |
|---|---|---|---|
| K0 | This plan (docs only; no deck edit) | 1 agent run | — |
| K1 | Geometry scrape + overlay report on A0 | 1 overlay pass | Second overlay that moves nodes |
| K2 | P0 already spent (JSON recorded) | 0 extra solves of A0 unless producing the missing four-file set | Re-solving A0 and silently changing the `.inp` |
| K3 | P1–P6 CCX 2.21 jobs | 6 primary + 3 numerical-control retries total (workflow.yaml cap) | 4th retry or any material/BC/load invention |
| K4 | Fetch hashed MCT case tables / ANSYS extract | 1 archive fetch + 1 MAPDL/ASCII retry | Fabricating INISTATE |
| K5 | Paper Methods/Results compile | 1 TeX pass after evidence exists | Writing 符合 from K0–K2 alone |
| K6 | GitHub Actions | A **catwalk** workflow that runs `ccx` on a hashed copy; not the Zhaqing prestress workflows | Treating 0-second failing Zhaqing runs as solves |

Human queries: **0**. Evaluation is by this agent with traces.

---

## 10. Required evidence objects

Every case that is allowed to enter Results must produce this closed set. **Go/No-Go lives in these objects**, not in chat.

| Object | Requirement | P0 status this turn |
|---|---|---|
| `.inp` | SHA-256 `974211b2…` or a **new** documented daughter hash | **Go** (file present, hash verified) |
| `.frd` | SHA-256; DISP block; 1125 nodes | **No-Go** (absent from tree and from commit `16e2d22`) |
| `.dat` | SHA-256; U and/or element field used for M1 | **No-Go** (absent) |
| `.sta` | SHA-256; increment row | **No-Go** (absent) |
| `.cvg` | SHA-256 | **No-Go** (absent) |
| Commit | Git SHA that contains the five files | P0 JSON: `16e2d22`. Four raw files: **unsupported** |
| Actions | Workflow that executed `ccx` on that hash | **No-Go.** Existing runs on this branch are `zhaqing-prestress-*`, conclusion `failure`, duration 0 s (e.g. `32868201652` on `0d7eaf5`) |

Sidecar `ccx_run.json` (SHA-256 `7e43993e42729e6f5b5b90ca1633b985177a8661dd81429874d073996f7d0733`) is **not** a substitute for the four raw files.

---

## 11. Stop rules

Stop the **scientific** claim (write FAIL/BLOCKED) but **do not stop reporting** and **do not mutate A0** when:

1. \(U_{\max} > 500\) mm (already true for P0).  
2. DISP missing.  
3. M2 unavailable without invention.  
4. Any frozen homemade hash would have to be edited to “make it run”.  
5. A temptation appears to publish 703.46 as Results.  
6. Git push to protected default, merge of PR #19, or opening a second PR is requested by automation — refuse those; keep writing on this branch.  
7. The only remaining idea is to swap `6712e918` or a homemade deck into main.

Do **not** stop because the ledger is stale, because Actions is the wrong workflow, or because the conclusion is ugly. Report those.

---

## 12. Failure criteria (process vs science)

| Class | Failure | Handling |
|---|---|---|
| Science | H-ZJG-CCX-OF-001 not met | Write FAIL. Keep A0. |
| Science | Huge \(U_{\max}\) | Write “likely failed static”. Locked for P0. |
| Process | Main deck bytes change | Protocol violation. Revert the `.inp`. |
| Process | Homemade written as 正路 | Protocol violation. |
| Process | 703.46 in Results | Protocol violation. |
| Process | Evidence object missing | Mark **unsupported** in the claim-trace. Do not fill with chat. |
| Ledger | `974211b2` not in `HASH_LEDGER.json` | Report: file is on the branch; ledger line absent. Do not call this “no main”. |

---

## 13. What is NOT tested

- 附件2-3 fourteen-mode spectrum and wind-tunnel frequencies.  
- Nonlinear form-finding to a bounded \(U_{\max}\) (P0 was `*STATIC` linear).  
- Dual-walkway S10 \(\leftrightarrow\) MCT 1:1 force map.  
- ANSYS MAPDL POST1 operating-force extract (currently blocked; stays blocked until a real table exists).  
- G14 code checks, load factors `gLCB*`, construction-stage time integration.  
- Homemade STEP coarsened/cleared decks as the official path.  
- `demo-rl-calculix`.  
- Zhaqing prestress command workflows as catwalk evidence.  
- Source-side prestress agreement (703.46).  
- Scientific 符合 of P0.

---

## 14. Skill and process map (pointer)

Each paper chapter maps to a skill and a gate. The English write-up is `02-mdpi-experiment-setup-draft.md`. Short index:

| Chapter function | Skills | Gate |
|---|---|---|
| Orchestration | N00 | G-ORCH |
| Charter / isolation | N01 | G0 |
| Sources, drawings, scrape | N02–N04 | G1–G3 |
| Semantics / abstraction | N05–N06 | G4–G5 |
| Geometry overlay | N07 | G6 |
| Materials / BC / prestress migrate | N08–N10 | G7, G8A, G8B |
| Load cases | N11 | G9 |
| Mesh / pre-solve / deck+solve | N12–N14 | G10–G12 |
| Solution verify / independent check | N15–N17 | G13, G15 |
| Paper / release | N18 | G16 |

N16 (code review) is **out of scope** for H-ZJG-CCX-OF-001.

---

## 15. Reproduction commands (plan freeze)

```
sha256sum catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp
# 974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1

cmp catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp \
    catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp
# silent, exit 0

sha256sum "catwalk-fem/mct-from-zero/source/01_设计资料与规范/猫道 - 门架索合建模型2.mct"
# 0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1

git rev-parse HEAD
# 0d7eaf5d79ba2daea55a7834d489001bb7fd9213   (at plan write)

ls catwalk-fem/eval/ccx_mct_from_zero/
# ccx_run.json only — no job.frd / job.dat / job.sta / job.cvg
```

End of preregistration.
