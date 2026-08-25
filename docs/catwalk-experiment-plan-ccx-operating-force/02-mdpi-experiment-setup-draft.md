# Materials and Methods (draft)

**Journal voice.** MDPI *Applied Sciences* research Article, IMRAD. This file is the Experiment Setup / Materials and Methods chapter draft. It maps each subsection to a skill design and a process design from the 19-node Bridge FEM Skill Suite. It does not claim scientific success.

**Preregistration.** Hypothesis `H-ZJG-CCX-OF-001` in `01-preregistration.md`. Include that identifier in any later submission Methods paragraph, as required by the journal instructions for computer-based studies.

**Generative-AI disclosure (required by MDPI when AI is used in design or analysis).** The modelling chain is itself the object of study: an agentic finite-element workflow executed by Cursor Grok agents on a Linux virtual machine, reading only `https://github.com/Hiram-test/model` and the hashed release assets named below. Agents wrote decks, invoked CalculiX 2.21, and drafted this chapter. Superficial copy-editing is not the disclosure; design, extraction, solve orchestration, and interpretation were agent-performed. No human was queried during this plan freeze.

---

## 2. Materials and Methods

### 2.1. Aim, object, and isolation protocol

The study tests whether an agentic finite-element chain can migrate a construction-catwalk model from a frozen MIDAS Civil NX archive and produce CalculiX operating forces that can be compared, eid by eid, with a same-source operating-force table. The physical object is the Zhangjinggao Yangtze crossing construction catwalk (portal frames and walking-rope system), not a completed stiffening girder and not the Zhaqing suspension-bridge exercise stored under `source-inputs/`.

Two classes of difficulty are isolated before any number is read.

*Technical difficulties.* A cable–beam mixed mesh must carry a §7.76 initial-stress card (element, integration point, six global Second Piola–Kirchhoff components), not an Abaqus-style ELSET-plus-uniaxial shortcut. Units jump from MIDAS kN·mm to CalculiX N·mm. A two-dimensional equivalent (\(Y\approx 0\)) is singular in the out-of-plane direction unless that constraint is taken from the source, not invented after a failed factorisation. Operating force is a post-solve field. Input prestress is not operating force.

*Object difficulties.* A construction catwalk has two walkways, two anchor families with different chainages, discrete portals (142 frames on the drawing-based homemade path; 71 truss elements on the MCT line model), and discrete cross-passages. Highway chainage is the only shared language between drawings and analysis. The official wind-tunnel frequency table (Attachment 2-3) is a *target after freeze*, not an input.

**Skill design.** Node 01 (`bridge-analysis-charter`, gate G0) freezes intended use, units, solver, and exclusions. Node 00 (`bridge-fem-workflow-orchestrator`) may not skip a blocked gate.

**Process design.** The charter for this experiment sets: solver = CalculiX 2.21; metric = operating force; geometry source = drawings if present, otherwise a full MCT scrape; forbidden results conclusion = source-side prestress 703.46 MPa versus ANSYS `INISTATE`; forbidden mains = homemade hashes `82548e6a`, `41fb3222`, `c635dad7`, `760c0ee4`, and trial `6712e918`. Attachment 2-3 frequencies remain in `catwalk-fem/isolated/TARGET-FREQ.json` and are not imported by the deck writer.

### 2.2. Sources, hashing, and drawing probe

All sources are identified by path and SHA-256. Bot transcripts are not evidence nodes.

The from-zero archive is MIDAS Civil NX 9.6.5 MCT `01_设计资料与规范/猫道 - 门架索合建模型2.mct` (448 673 B, SHA-256 `0d18e3f7b009e0306fb4b9f3051b4a16d05fa24d9e966774e809b8942a4f22e1`, encoding GB18030). The file contains 1 125 nodes, 1 123 `TENSTR` cables, 71 `TRUSS` portals, `*INIFORCE` on every cable, `*INI-EFORCE`, `*EQUI-MFORCE`, seven static load cases, and the stage `一次成桥`.

The ANSYS control is release `catwalk-attachment23-v2.0-s10-20260716`, file `cw_S10_0716t050342_a4_eq.db`, SHA-256 `17e0bac8717e7c32a407571d33e38dd777736b31b6656684e53449fa8c9d40fd`. On this virtual machine a MAPDL extract was not obtained; an ASCII probe counted zero `INISTATE` / `LINK180` / `PRESTRESS` keys. That absence is recorded. No table is fabricated.

Zhangjinggao catwalk construction drawings (DWG/DXF) are **not** in the working tree. The DWG set under `source-inputs/zhaqing-suspension-bridge/drawings/` belongs to a different bridge and is excluded. Theory PDFs under `catwalk-theory/` are not drawings.

**Skill design.** N02 ingestion (G1) writes `source_manifest` and hashes. N03 drawing extraction (G2) and N04 registration (G3) run a drawing probe and must emit either a sheet register or an explicit `drawings_absent` flag.

**Process design.** Because the probe is `drawings_absent`, the geometry overlay uses a full MCT scrape (Section 2.3). Archive directory `03_猫道动力分析/MCT基准复现_V1.0/` is indexed only; its CSV members may later serve as *control tables* after a hash-closed fetch against `archive_index_MCT基准复现_V1.0.json`. They are not a new main model.

### 2.3. Geometry overlay (same-source)

Overlay is same-source by preregistration. If drawings exist, analysis nodes are projected onto drawing stations. If drawings are absent, the MCT node table is the reference and the CalculiX `*NODE` block must reproduce it.

The locked deck `catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp` (SHA-256 `974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1`, 930 300 B) was emitted by `catwalk-fem/mct-from-zero/emit_ccx.py` from the MCT body. This-turn independent count: 1 125 unique nodes, \(X\in[831091,5101700]\) mm, span \(4270.609\) m, \(Y=0\) line model. A byte-identical copy exists at `catwalk-fem/mct-from-zero/artifacts/mct_from_zero_static.ccx.inp`.

A millimetre centre-line STEP of the dual walkway (SHA-256 `d03d01e3…`) is a different mesh. It is not a 1:1 partner of the 1 194-element MCT model and is not used to move A0 nodes.

**Skill design.** N05 semantic inventory (G4) labels cables, portals, and load paths from MCT groups (`猫道索`, `门架索`, `门架`, span groups). N06 abstraction (G5) records `TENSTR→T3D2` and `TRUSS→B31` (the latter because 35 portal members lie on \(Z\) and cannot form a T3D2 first normal). N07 topology (G6) writes `fem_geometry_ir` and `geometry_overlay_report`.

**Process design.** Overlay pass = 1 125/1 125 coordinate identity at the printed `.inp` precision. Failures that “fix” geometry by editing `974211b2` are protocol violations. Homemade STEP decks remain frozen failure scenes and are not the official path.

### 2.4. Materials, sections, supports, and prestress migration

Materials and sections are read from the MCT `*MATERIAL` and `*SECTION` blocks. Cable steel uses \(E=1.20\times 10^{5}\,\mathrm{N/mm}^2\); Q235 uses \(E=2.06\times 10^{5}\,\mathrm{N/mm}^2\). Areas are \(A_1=\pi(168.498/2)^2\) mm² for the walkway rope, \(A_2=\pi(103.436/2)^2\) mm² for the portal rope, and a double box \(2\times\mathrm{B}\,160\times 4\) for the 71 frames. Mass density is converted from MCT specific weight with \(g=9806\,\mathrm{mm\,s}^{-2}\). No numerical value is typed by hand.

Supports follow MCT `*CONSTRAINT` (UX/UY/UZ flags 111000 and 011000 on named nodes of stage `一次成桥`). Because the MCT model is a \(Y\approx 0\) equivalent, UY is also restrained on every node. That plane restraint is a migrate of an implicit MCT condition, recorded in the deck comment; it is not a homemade pin set.

Prestress is present in the MCT (`*INIFORCE` 1 123, `*INI-EFORCE` 1 123). The migrate writes `*INITIAL CONDITIONS, TYPE=STRESS` as 8 984 rows (\(1\,123\times 8\)): element, integration point, six global PK2 components obtained by projecting \(\sigma=F/A\) along the element axis, with \(F\) the INI-EFORCE mean when present. This-turn reread of eid 1 gives a PK2 trace of \(703.4605\,\mathrm{N/mm}^2\), equal to \(15\,686\,250 / 22\,298.69164950066\). **That identity is source-side prestress. It is excluded from Results.** A numerical closeness of this \(\sigma\) to an ANSYS `INISTATE` value of 703.46280 (relative \(3.19\times 10^{-6}\)) is likewise source-to-source and is not a `974211b2` solve.

**Skill design.** N08 properties (G7), N09 boundaries (G8A), N10 initial state (G8B). N10’s job in *this* experiment is migration of an existing initial-force field, not a new form-finding that replaces A0.

**Process design.** “From zero” means: parse the MCT body; do not start from archive CSV; do not start from a homemade STEP deck. First physics slice: statics, cable force, prestress. ANSYS is compared when an extract exists; it is not invented.

### 2.5. Load cases and combinations

MCT `*STLDCASE` names, read from the hashed file, are 自重, 二期, 整体降温15, 整体降温34, 施工风荷载, 最大阵风, and 施工荷载. Stage `一次成桥` applies 自重 and 二期. `*LOADCOMB` names 工况1恒载 through 工况6恒+施工+温34 are the operating-force cases P1–P6.

The locked deck currently contains one linear `*STATIC` step with gravity on `E_CABLE`/`E_FRAME` and nodal 二期 `*CLOAD`. That step is case P0. Output requests are `*NODE FILE`/`*NODE PRINT` U and `*EL FILE`/`*EL PRINT` S (and E on the file request). Operating force M1 must be recovered with an explicit formula in the run record (stress times area, or a later `NFORC` request on a daughter deck). The main file is not edited to add cards.

**Skill design.** N11 load cases (G9) writes `load_plan`, `combination_plan`, and a resultant ledger. Each `*CLOAD`/`*DLOAD` must close against the MCT resultant.

**Process design.** P1–P6, if run, are new hashed decks. Temperature and wind magnitudes come from the MCT scrape. Load factors `gLCB*` (1.2/1.4/1.1/1.05) are **not** in the H-ZJG-CCX-OF-001 matrix.

### 2.6. Discretisation, pre-solve verification, and solver execution

N12 (G10) records the mixed mesh: 1 123 two-node trusses and 71 B31 beams, first normal `(1,1,1)` on beams. N13 (G11) is a pre-solve gate: object counts, IC format, constraint rank, and isolation from TARGET-FREQ. Passing G11 is not a solve.

N14 (G12) is the only node allowed to invoke CalculiX. Rules taken from the skill contract: clean job directory; unique SOLVE-ID; adapter version recorded; exit 0 is completion, not verification; raw results are hashed read-only.

**Locked P0 compute conclusions** (CalculiX 2.21, deck `974211b2`; may be physically bad; still reported):

- process exit 0;
- \(U_{\max}=9.264\times 10^{9}\) mm;
- eid 1 axial force \(15\,687\,915\) N versus the sidecar MCT number \(15\,686\,250\) N.

These three facts are compute conclusions. They are not 符合 Attachment 2-3. A displacement of order \(10^{9}\) mm is written as a **likely failed static**. The commit that recorded the JSON summary is `16e2d222d3e7dc1b503d528d2dea621f1bcbcffa`. That commit does not contain `.frd`, `.dat`, `.sta`, or `.cvg`. Therefore P0 is **not** evidence-complete under Section 2.8.

Homemade scenes remain in the archive as negative controls: `82548e6a` (illegal IC card), `41fb3222` (singular tangent), `c635dad7` (four unconstrained B31 components), `760c0ee4` (those twelve nodes pinned; no solve delivered). Trial `6712e918` is absent and died at SPOOLES. None of them is promoted.

### 2.7. Solution verification and independent check

N15 (G13) answers whether the discrete equations were solved. Mandatory checks: DISP completeness; increment presence in `.sta`; residual/`.cvg`; global force balance; a free-body cut on one walkway-rope group. N17 (G15) is the independent check: MCT operating-force table (or ANSYS table if extracted) versus CCX M1, using the pre-registered median and p95 on \(\delta(eid)\). N16 code review is out of scope.

**Skill design.** G13 cannot consume a chat message. G15 cannot share the migrate script as its only independent path: the referent table must come from MCT/ANSYS results, not from re-reading `*INIFORCE`.

**Process design.** Pre-registered scientific PASS requires DISP on 1 125 nodes, \(U_{\max}\le 500\) mm, a true operating-force table as M2, median \(\delta\le 0.01\), p95 \(\delta\le 0.05\), and the six evidence objects of Section 2.8. P0 already fails the displacement gate and the M2 definition gate. That failure is the written conclusion.

### 2.8. Evidence objects, Actions, and Go/No-Go

A result sentence may be written only if the following objects exist: `.inp`, `.frd`, `.dat`, `.sta`, `.cvg`, the git commit that stores them, and a GitHub Actions run that executed `ccx` on that hash. Each file carries SHA-256. Go/No-Go is evaluated *inside* that set.

At plan freeze:

| Object | Go/No-Go |
|---|---|
| Main `.inp` `974211b2` | Go |
| `.frd` / `.dat` / `.sta` / `.cvg` for P0 | No-Go (not in tree) |
| Commit of raw P0 results | No-Go |
| Actions | No-Go. Branch runs `zhaqing-prestress-calibration.yml`, `zhaqing-prestress-delegated.yml`, and `zhaqing-prestress-pr-dispatch.yml` fail in 0 s (example run `32868201652` on `0d7eaf5`). They are the wrong object. |

`HASH_LEDGER.json` still names homemade `760c0ee4` as `new_main`. The migrate file is nevertheless on the branch. The ledger line is reported as stale; the deck is not rewritten.

### 2.9. Paper process and what is not done

N18 (G16) assembles the engineering report and the machine release bundle. The paper’s Introduction states the technical and catwalk-object difficulties of Section 2.1. Subsequent sections follow the skill order N02–N17. Results may quote the locked P0 facts. Results may not quote 703.46 as a successful comparison. Results may not say 符合 without a DISP-bearing four-file set.

Not tested: Attachment 2-3 frequencies; dual-walkway 1:1 map; ANSYS POST1 table (blocked); design combinations `gLCB*`; homemade STEP as the official path; `demo-rl-calculix`.

### 2.10. Software, versions, and data availability

- CalculiX 2.21 (banner recorded in prior frozen jobs on this branch).  
- Python 3 for `catwalk-fem/mct-from-zero/{parse_mct.py,emit_ccx.py,build.py}`.  
- Git repository `https://github.com/Hiram-test/model`, branch `cursor/catwalk-main-deck-gate-f23d`.  
- Skill suite `bridge-fem-skill-suite` v1.0.0 (19 `SKILL.md` files, `workflow.yaml`).  
- Preregistration path `docs/catwalk-experiment-plan-ccx-operating-force/`.  

Data that exist are the hashed MCT, the hashed migrate `.inp`, and the P0 JSON sidecar. Data that do not exist are the P0 raw solver files and an ANSYS operating-force extract. Both absences are part of the experimental record.

---

**End of Methods draft.** Do not paste this chapter into Results. Do not upgrade P0 to 符合 in production typesetting.
