# Claim-to-artifact trace

Hypothesis `H-ZJG-CCX-OF-001`. Bot chat is **not** a node. A row is **unsupported** when any of commit / Actions / hashed solver artifact is missing or is the wrong object.

Legend: **Go** = object exists and hash-closes. **No-Go** = required object missing or wrong. **Sidecar-only** = JSON/text exists but is not a raw solver file. **Excluded** = forbidden as a results conclusion.

Head at plan write: `0d7eaf5d79ba2daea55a7834d489001bb7fd9213` on `cursor/catwalk-main-deck-gate-f23d`. PR #19 `merged=false`.

---

## A. Planned Methods / Results sentences

| ID | Planned sentence (paper) | Commit | Actions | Hashed solver / source artifact | Status |
|---|---|---|---|---|---|
| S01 | The main CalculiX deck is the MCT migrate `zjg_catwalk_migrate_main.inp`. | `0d7eaf5` added the path on #19. | Zhaqing workflows on `0d7eaf5` (`32868201652`, `32868200688`, `32868199639`) failed in 0 s; **wrong object**. | SHA-256 `974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1` (this-turn `sha256sum`). | **Supported as file identity.** Actions node unsupported. |
| S02 | The deck has 1125 nodes, 1123 T3D2, 71 B31, span 4270.6 m, coordinates in MCT mm. | Count is in `mct_from_zero_inp_meta.json` (commit `16e2d22` / `ed14366` line). | None that counted nodes. | This-turn reread of `974211b2`: 1125 unique nodes, 1123 T3D2, 71 B31, \(\Delta X=4270609\) mm. | **Supported** by hashed `.inp`. |
| S03 | Initial conditions are 8984 eight-field PK2 rows (\(1123\times 8\)). | Same deck commits. | None. | This-turn count: 8984 rows, 1123 eids, ends at `*BOUNDARY`. | **Supported** by hashed `.inp`. |
| S04 | Geometry overlay used construction drawings. | — | — | Zhangjinggao catwalk DWG/DXF: **absent**. Zhaqing DWGs: wrong object. | **Unsupported / false.** Protocol falls through to MCT scrape. |
| S05 | Because drawings were absent, the MCT body was scraped and overlaid. | Parse/emit: `ef52a7f`…`16e2d22`. Sidecar `0d7eaf5`. | Wrong-object Zhaqing runs. | MCT SHA-256 `0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1`. Overlay residual table `geometry_overlay_report.json`: **not present** as a closed G6 artifact for A0. | **Partially supported** (scrape exists). Overlay report: **unsupported**. |
| S06 | Prestress exists in the MCT (`*INIFORCE` 1123). | `0d7eaf5` sidecars `SIDECAR_MCT_INIFORCE_1123.json`. | Wrong object. | MCT body + sidecar SHA-256 `2fac3bd449fa8d203417c2ea3694b9452fc8b934a3dd5d5d4d354a6e3aeb7fcc`. | **Supported as source fact.** Not a CCX result. |
| S07 | ANSYS S10 `.db` is the hashed control `17e0bac8…`. | Cited in `ANSYS_SOURCE_SEARCH.json` / sidecars on `0d7eaf5`. | None extracted the `.db`. | Release asset hash recorded; extract `extracted=false`. | **Supported as source identity.** Operating-force table: **unsupported**. |
| S08 | CalculiX 2.21 completed a linear static on `974211b2` with exit 0. | `16e2d22` wrote `eval/ccx_mct_from_zero/ccx_run.json`. | No Actions job ran `ccx` on this deck. | Sidecar SHA-256 `7e43993e42729e6f5b5b90ca1633b985177a8661dd81429874d073996f7d0733`. | **Locked compute conclusion** (exit 0). Actions **unsupported**. |
| S09 | Displacement authority is `.dat` \(U_{\max}=9.26\times 10^{9}\) mm on 1125 original-node U; **机构型**. | Same solve as S08. | None. | Authority = `.dat` original-node U, not FRD. | **Locked compute conclusion.** Mechanism-type. Do not write 符合. |
| S09b | The first `.frd` DISP block is a second, independent \(U_{\max}\). | — | — | First FRD DISP has **0 original NSET nodes** because T3D2 is expanded to C3D8I; original NSET is not on the FRD mesh. | **Excluded / false.** Not a second displacement conclusion. |
| S10 | eid 1 operating force was \(15\,687\,915\) N versus MCT \(15\,686\,250\) N. | Same JSON `named_N["1"]`. | None. | Sidecar MCT number is INI-EFORCE mean, **not** an operating-force table. | **Locked compute pair.** H-ZJG-CCX-OF-001 test: **unsupported** (wrong M2). |
| S10b | S≈IC means the cables are in force balance. | — | — | Worst relative −19.1%. | **Excluded / false.** S≈IC is **not** cable-force balance. |
| S11 | The static state is balanced / 符合附件2-3. | — | — | `.dat` \(U_{\max}\) is 机构型. S≈IC worst −19.1%. TARGET-FREQ isolated. | **Excluded / false.** Do not write 符合. |
| S12 | Source prestress 703.46 MPa matches ANSYS INISTATE 703.46280. | — | — | This-turn IC eid 1 PK2 **trace** = 703.4605 N/mm² = \(F/A\) from MCT INI-EFORCE. ANSYS INISTATE extract = 0 keys. | **Excluded as results.** Allowed only in Methods as “what we refuse to treat as success”. |
| S13 | Homemade decks `82548e6a` / `41fb3222` / `c635dad7` / `760c0ee4` are the official path. | Those files are on #19 (`checksums.sha256`). | Zhaqing Actions, wrong object. | Hashes verified this turn; roles = frozen **failure** scenes. | **Excluded.** Trace them only as negative controls. |
| S14 | Trial deck `6712e918` is a usable main. | Not in this tree (`rg` empty). | — | Absent; brief says SPOOLES death. | **Unsupported / excluded.** Do not swap. |
| S15 | P1–P6 operating-force cases were solved in CCX and compared to MCT case tables. | — | — | Archive index lists `mct_case_{1..6}_element_force.csv` hashes; **CSV bodies not in tree**. No CCX jobs for P1–P6. | **Unsupported** (planned, not run). |
| S16 | GitHub Actions reproduced the P0 solve. | `0d7eaf5` / `16e2d22`. | `zhaqing-prestress-*` failure, 0 s. | No catwalk `ccx` workflow. | **Unsupported.** |
| S17 | `HASH_LEDGER.json` already lists `974211b2` as `new_main`. | Ledger last edited in the 760c0ee4 delivery commits. | — | File content: `new_main` = `760c0ee4`. | **False.** Report: ledger stale; deck present. |
| S18 | Nineteen skills were executed end-to-end with passing gates G0–G16. | Suite is in `bridge-fem-skill-suite/`. | — | No `gate_ledger.json` for A0 G6/G12/G13/G15. | **Unsupported** as a completed run. Design mapping: see Methods draft. |
| S19 | VM success equals scientific reproduction. | — | — | Preregistration §1 forbids this. | **Excluded.** |

---

## B. Evidence objects for P0 (must all be Go before any Results 符合 — and 符合 is still forbidden on 机构型 \(U_{\max}\))

| Object | Path | SHA-256 | Commit | Actions | Go/No-Go |
|---|---|---|---|---|---|
| `.inp` | `catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp` | `974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1` | `0d7eaf5` | wrong workflow | **Go** (file) |
| `.inp` copy | `catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp` | same | `16e2d22` | wrong workflow | **Go** (byte-identical) |
| `.frd` first DISP | FRD mesh after T3D2→C3D8I | — | — | — | **Not a U conclusion** (0 original NSET nodes) |
| `.dat` original-node U | P0 `.dat` | — | — | — | **Authority:** \(U_{\max}=9.26\times 10^{9}\) mm, 1125 nodes, 机构型 |
| `.sta` | — | — | not in `16e2d22` | — | **No-Go** |
| `.cvg` | — | — | not in `16e2d22` | — | **No-Go** |
| JSON sidecar | `catwalk-fem/eval/ccx_mct_from_zero/ccx_run.json` | `7e43993e42729e6f5b5b90ca1633b985177a8661dd81429874d073996f7d0733` | `16e2d22` | — | **Sidecar-only** |
| MCT source | `…/猫道 - 门架索合建模型2.mct` | `0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1` | on branch | — | **Go** (source) |
| ANSYS `.db` | release asset | `17e0bac8717e7c32a407571d33e38dd777736b31b6656684e53449fa8c9d40fd` | not a git blob | — | **Go** as hash citation; extract **No-Go** |

---

## C. Frozen homemade (negative controls only)

| Hash prefix | Path | SHA-256 | Role | Main? |
|---|---|---|---|---|
| 82548e6a | `artifacts/zjg_catwalk_coarsened.inp` | `82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da` | ELSET+uniaxial fail | No |
| 41fb3222 | `artifacts/zjg_catwalk_ccx221.inp` | `41fb32225489b0c6f993d3a077ce9293d472e4ede5ff644ca170bebbbbca924a` | singular IC-pass | No |
| c635dad7 | `artifacts/zjg_catwalk_main.inp` | `c635dad78661e6495bdf829b0c97f8610b5fedb8603307e806860032a70cda84` | 4 B31 unconstrained | No |
| 760c0ee4 | `artifacts/zjg_catwalk_cleared.inp` | `760c0ee44d7077ddfb84273cba916abb1fea1eb2a0ff6cfe57abaec9b0585de9` | cleared homemade | No |
| 6712e918 | — | — | SPOOLES death; absent | No |

This-turn `sha256sum` on the four present files matched the table.

---

## D. Actions inventory (why every Actions cell is No-Go for H-ZJG-CCX-OF-001)

Workflows in `.github/workflows/` are named `zhaqing-native-command.yml` and `zhaqing-prestress-*.yml`. They are the Zhaqing prestress command path, not a Zhangjinggao catwalk CCX job.

Latest on this branch (head `0d7eaf5`):

| Run ID | Workflow | Conclusion | Duration | Usable for P0? |
|---|---|---|---|---|
| 32868201652 | zhaqing-prestress-calibration | failure | 0 s | No |
| 32868200688 | zhaqing-prestress-delegated | failure | 0 s | No |
| 32868199639 | zhaqing-prestress-pr-dispatch | failure | 0 s | No |

A future catwalk workflow must hash the `.inp`, run `ccx`, and upload `.frd/.dat/.sta/.cvg`. Until that exists, every Results sentence that needs Actions stays **unsupported**.

---

## E. How to add a supported row later

1. Do not edit `974211b2`.  
2. Run `ccx` in a new directory; write the four raw files; `sha256sum` them.  
3. Commit those files on this branch.  
4. Trigger a catwalk Actions workflow that repeats the job.  
5. Fill M1 from hashed `.dat` (or a later explicit force request), M2 from a hashed operating-force table (not INIFORCE, not S≈IC).  
6. Take \(U_{\max}\) from `.dat` original-node U only. Do not use first FRD DISP.  
7. Only then flip a row from unsupported to supported.  
8. Still do not write 符合 if `.dat` \(U_{\max}\) remains \(9.26\times 10^{9}\) mm (机构型).
