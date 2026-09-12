# Zhangjinggao catwalk — CCX operating-force experiment plan

This folder is the **preregistration + MDPI Materials-and-Methods draft** for the agentic-FEA paper on the Zhujiang / Zhangjinggao construction catwalk.

It is a new-conversation Grok Build plan. It does **not** rewrite the locked main deck.

| File | Role |
|---|---|
| [`locked-objects.json`](locked-objects.json) | Machine-readable locked hashes and compute facts |
| [`01-preregistration.md`](01-preregistration.md) | Hypothesis, cases, overlay protocol, metrics, stop rules, Go/No-Go |
| [`02-mdpi-experiment-setup-draft.md`](02-mdpi-experiment-setup-draft.md) | English MDPI Methods chapter; maps each block to a skill + process |
| [`03-claim-to-artifact-trace.md`](03-claim-to-artifact-trace.md) | Planned sentence → commit → Actions → hashed solver object |
| [`04-self-eval-evidence-trace.md`](04-self-eval-evidence-trace.md) | Self-evaluation with command traces; no user questions |

**Object under test:** CalculiX operating force (运营力), not source-side prestress 703.46.

**Locked main deck:** `catwalk-fem/artifacts/zjg_catwalk_migrate_main.inp`  
SHA-256 `974211b2ddfe2950548ee2455bc22e1e2e68d3e1f53df4c4e1eb71ece0267fd1`

**Executed overlay (same branch, does not rewrite the main):** `catwalk-fem/eval/plan_974211b2/` — MCT alignment scrape + prestress restack + IC reread. Ledger now lists `974211b2` as `current_main`.

**Locked P0 displacement authority:** `.dat` \(U_{\max}=9.26\times 10^{9}\) mm on 1125 original-node U. **机构型 (mechanism-type).** The first `.frd` DISP block with 0 original NSET nodes is **not** a second displacement conclusion (T3D2 expanded to C3D8I; original NSET is not on the FRD mesh). **S≈IC is not cable-force balance** (worst −19.1%). 703.46 stays out of Results. Do not write 符合.

**Not a scientific success document.** VM success is not a scientific claim.
