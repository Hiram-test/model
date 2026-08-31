#!/usr/bin/env python3
"""Knowledge graph of the true-3D catwalk chain (模型 / 模态 / 工况 / 门禁 / 图谱).

Nodes and directed edges, JSON + GraphML-ish CSV. Built only from artifacts
already on disk. No invented frequencies or RMS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ART = BASE / "artifacts"


def node(nid, typ, label, **props):
    d = {"id": nid, "type": typ, "label": label}
    d.update(props)
    return d


def edge(src, rel, dst, **props):
    d = {"source": src, "rel": rel, "target": dst}
    d.update(props)
    return d


def main() -> None:
    man = json.loads((ART / "true3d_model_manifest.json").read_text())
    gates = json.loads((ART / "gate_status.json").read_text())
    pair = pd.read_csv(ART / "true3d_table41_pairing.csv")
    modes = pd.read_csv(ART / "true3d_mode_table.csv")
    lib = json.loads((ART / "extreme_weather_library.json").read_text())
    sweep = pd.read_csv(ART / "extreme_sweep_responses.csv")
    ext = json.loads((ART / "attach23_extract.json").read_text())

    nodes, edges = [], []
    nodes.append(node("s10", "source", "S10 V2.0 APDL",
                      mass_t=man["mass_ledger_t"]["s10_reference"]))
    nodes.append(node("deck", "model", "true3d_ccx.inp",
                      sha=man["deck_sha256"], coarsen=man["coarsen"],
                      nodes=man["nodes_total"], elements=man["elements_total"]))
    edges.append(edge("s10", "SIMPLIFIED_BY", "deck", contract="R1-R7"))

    for k, g in man["groups"].items():
        nid = f"line:{k}"
        nodes.append(node(nid, "rope_line", k, n_ropes=g["n_ropes"],
                          y_eq_m=g["y_eq_m"], A_eq_mm2=g["A_eq_mm2"]))
        edges.append(edge("deck", "HAS_LINE", nid))

    nodes.append(node("portals", "component", "142 parametric portals", n=man["portals"]))
    nodes.append(node("passages", "component", "passage stations",
                      n_stations=man["passages"],
                      raw_x=man.get("passages_raw_x_stations"),
                      note=man.get("passages_note", "R5 equivalent beams")))
    edges.append(edge("deck", "HAS", "portals"))
    edges.append(edge("deck", "HAS", "passages"))

    for gname in ("G-P1", "G-P2", "UY", "G-P3", "G-P4"):
        rec = gates.get(gname, {})
        if not isinstance(rec, dict):
            continue
        nid = f"gate:{gname}"
        keep = {k: rec[k] for k in rec if k in ("pass", "verdict", "rel", "uy_frac")}
        nodes.append(node(nid, "gate", gname, **keep))
        edges.append(edge("deck", "CHECKED_BY", nid))

    struct = modes[~modes.residual_zero.astype(bool)]
    for fam in "LVT":
        nid = f"family:{fam}"
        n = int((struct.family == fam).sum())
        nodes.append(node(nid, "mode_family", f"{fam} family", n_modes=n))
        edges.append(edge("deck", "HAS_FAMILY", nid))

    for _, r in pair.iterrows():
        nid = f"table41:{r.reference_id}"
        nodes.append(node(nid, "table41_row", r.reference_id,
                          reference_hz=float(r.reference_hz),
                          matched_hz=float(r.matched_hz),
                          rel_pct=float(r.relative_error_percent)))
        edges.append(edge(nid, "COMPARED_TO", "attach23",
                          note="comparison_only"))
        if pd.notna(r.matched_mode):
            edges.append(edge(nid, "PAIRED_WITH", f"mode:{int(r.matched_mode)}"))

    nodes.append(node("attach23", "document", "附件2-3",
                      usage=ext.get("usage"),
                      sha=ext.get("sha256_prefix")))

    for _, r in struct.iterrows():
        nid = f"mode:{int(r['mode'])}"
        nodes.append(node(nid, "mode", f"mode {int(r['mode'])}",
                          f_hz=float(r.f_hz), family=r.family, parity=r.parity,
                          half_waves=int(r.half_waves)))
        edges.append(edge(nid, "IN_FAMILY", f"family:{r.family}"))

    for sc in lib["scenarios"]:
        nid = f"event:{sc['id']}"
        sw = sweep[sweep.id == sc["id"]]
        extra = {}
        if len(sw):
            extra = {"U10": float(sw.iloc[0].U10),
                     "rms_L_max_mm": float(sw.iloc[0].rms_L_max_mm),
                     "stationarity": sw.iloc[0].stationarity}
        nodes.append(node(nid, "wind_event", sc["id"],
                          category=sc["category"], confidence=sc.get("confidence"),
                          **extra))
        edges.append(edge(nid, "DRIVES", "channel:L"))
        edges.append(edge(nid, "DRIVES", "channel:V"))
        edges.append(edge(nid, "DRIVES", "channel:Tcw"))
        edges.append(edge(nid, "DRIVES", "channel:Tg"))

    for ch in ("L", "V", "Tcw", "Tg"):
        nodes.append(node(f"channel:{ch}", "response_channel", ch))
        edges.append(edge("deck", "OUTPUTS", f"channel:{ch}"))

    nodes.append(node("atlas", "product", "response atlas A1-A5"))
    nodes.append(node("warning", "system", "early-warning state machine"))
    nodes.append(node("galloping", "workshop", "陡振 Den Hartog"))
    for a in ("atlas", "warning", "galloping"):
        edges.append(edge("deck", "FEEDS", a))
    edges.append(edge("atlas", "QUERIED_BY", "warning"))

    graph = {
        "schema": "catwalk-true3d-kg/v0",
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "nodes": nodes,
        "edges": edges,
        "claim": "inventory graph of this run; not a scientific conclusion",
    }
    (ART / "knowledge_graph.json").write_text(
        json.dumps(graph, indent=1, ensure_ascii=False))
    pd.DataFrame(nodes).to_csv(ART / "knowledge_graph_nodes.csv", index=False)
    pd.DataFrame(edges).to_csv(ART / "knowledge_graph_edges.csv", index=False)
    print(f"nodes {len(nodes)}  edges {len(edges)}")


if __name__ == "__main__":
    main()
