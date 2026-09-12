"""Plot main-span observables of the eleven named Table 4-1 rows (ccx model)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150

ART = Path("/workspace/catwalk-fem/agentic-fea/artifacts")

pairing = pd.read_csv(ART / "ccx_table41_pairing.csv")
obs_all = np.load(ART / "ccx_mode_observables_first24.npy", allow_pickle=True)
obs_by_mode = {int(o["mode"]): o["obs"] for o in obs_all}

named = pairing[~pairing["reference_id"].str.startswith("SIDE")]
fig, axes = plt.subplots(4, 3, figsize=(13, 11), sharex=True)
axes = axes.ravel()
fam_of = {"L": "L 共横移", "V": "V 共竖移", "T": "T 幅间差分竖向"}
for ax, (_, row) in zip(axes, named.iterrows()):
    rid = row["reference_id"]
    mode = int(row["matched_mode"])
    fam = rid[0]
    obs = obs_by_mode.get(mode)
    if obs is None:
        ax.axis("off")
        continue
    pts = sorted(obs[fam], key=lambda t: t[0])
    xs = np.array([p[0] for p in pts])
    vs = np.array([p[1] for p in pts])
    sel = (xs >= 1553.4) & (xs <= 3818.6)
    v = vs[sel]
    v = v / (np.max(np.abs(v)) or 1.0)
    ax.plot(xs[sel], v, lw=1.3, color={"L": "#1f618d", "V": "#117a65", "T": "#b03a2e"}[fam])
    ax.axhline(0, color="#95a5a6", lw=0.5)
    ax.set_title(
        f"{rid}: M{mode}  {row['matched_hz']:.5f} Hz  ({row['relative_error_percent']:+.2f}%)",
        fontsize=10,
    )
    ax.set_ylabel(fam_of[fam], fontsize=8)
    ax.grid(ls=":", alpha=0.4)
axes[-1].axis("off")
fig.suptitle("ccx 全三维双 MCT：十一个具名行配对模态的主跨观测量（归一化）", fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.97))
fig.savefig(ART / "ccx_named_mode_shapes.png", bbox_inches="tight")
print("wrote", ART / "ccx_named_mode_shapes.png")
