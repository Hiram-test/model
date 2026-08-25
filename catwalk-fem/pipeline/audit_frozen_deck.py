#!/usr/bin/env python3
"""Read-only audit of the frozen hashed deck. Never rewrite the .inp."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    N_CROSS_PASSAGES,
    N_PORTALS_BOTH_DECKS,
    N_PORTALS_PER_DECK,
    PASSAGE_LABELS,
    PASSAGE_X,
    PORTAL_X,
    SPAN_BREAKS_NOMINAL,
)
from coord import write_json  # noqa: E402
from formfind import initial_state  # noqa: E402
from reconcile import sha256_file  # noqa: E402

FROZEN_SHA256 = "82548e6a3bd2612b6b39a08c313402b32a1961af6eba018158267906276ab6da"
FROZEN_BYTES = 7_702_117
FROZEN_NAME = "zjg_catwalk_coarsened.inp"
CCX221_IC_FIELDS = (
    "element_number",
    "integration_point",
    "Sxx",
    "Syy",
    "Szz",
    "Sxy",
    "Sxz",
    "Syz",
)


def _span_of(x: float) -> str:
    if x < SPAN_BREAKS_NOMINAL[1]:
        return "north_660"
    if x < SPAN_BREAKS_NOMINAL[2]:
        return "main_2300"
    if x < SPAN_BREAKS_NOMINAL[3]:
        return "south_717"
    return "south_503"


def _chainage(x: float) -> str:
    total = 16_000.0 + 876.0 + float(x)
    km = int(total // 1000)
    rem = total - 1000 * km
    return f"K{km}+{rem:07.3f}"


def classify_ic_line(raw: str) -> dict:
    parts = [p.strip() for p in raw.split(",") if p.strip() != ""]
    first = parts[0] if parts else ""
    elset_like = bool(re.match(r"^[A-Za-z_]", first or ""))
    n_fields = len(parts)
    uniaxial = n_fields == 2
    ccx221_legal = (not elset_like) and n_fields == 8
    return {
        "raw": raw,
        "fields": parts,
        "n_fields": n_fields,
        "first_token": first,
        "elset_plus_uniaxial": elset_like and uniaxial,
        "ccx_2_21_legal": ccx221_legal,
        "reason": (
            "ELSET name + one axial stress; CalculiX 2.21 §7.76 TYPE=STRESS "
            "requires element number, integration point, Sxx Syy Szz Sxy Sxz Syz"
            if elset_like and uniaxial
            else ("ccx 2.21 eight-field row" if ccx221_legal else "unrecognized TYPE=STRESS row")
        ),
    }


def parse_initial_conditions(text: str) -> dict:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.upper().startswith("*INITIAL CONDITIONS") and "STRESS" in line.upper():
            start = i
            break
    if start is None:
        return {"present": False, "rows": []}
    rows = []
    for line in lines[start + 1 :]:
        if not line or line.startswith("**"):
            continue
        if line.startswith("*"):
            break
        rows.append(classify_ic_line(line))
    return {
        "present": True,
        "keyword_line": lines[start],
        "keyword_line_no": start + 1,
        "rows": rows,
        "all_elset_uniaxial": bool(rows) and all(r["elset_plus_uniaxial"] for r in rows),
        "any_ccx_2_21_legal": any(r["ccx_2_21_legal"] for r in rows),
    }


def parse_nset(text: str, name: str) -> list[int]:
    lines = text.splitlines()
    ids: list[int] = []
    capture = False
    for line in lines:
        if line.upper().startswith("*NSET") and f"NSET={name}".upper() in line.upper():
            capture = True
            continue
        if capture:
            if line.startswith("*"):
                break
            if line.startswith("**"):
                continue
            for tok in line.replace(",", " ").split():
                if tok.isdigit():
                    ids.append(int(tok))
    return ids


def count_boundary_cards(text: str) -> dict:
    names = []
    pending = False
    for line in text.splitlines():
        if line.startswith("*BOUNDARY"):
            pending = True
            continue
        if pending:
            if line.startswith("**"):
                continue
            names.append(line.split(",")[0].strip())
            pending = False
    return {"n_cards": len(names), "sets": names}


def audit_frozen_inp(inp_path: Path) -> dict:
    data = inp_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8")
    ic = parse_initial_conditions(text)
    floor = parse_nset(text, "N_FLOOR_ANCHOR")
    portal = parse_nset(text, "N_PORTAL_ANCHOR")
    overlap = sorted(set(floor) & set(portal))
    state = initial_state()
    sigma_line = None
    for row in ic.get("rows", []):
        if row["first_token"] == "E_FLOOR_ROPE":
            sigma_line = row
            break
    return {
        "path": str(inp_path),
        "bytes": len(data),
        "sha256": digest,
        "frozen_sha256": FROZEN_SHA256,
        "hash_unchanged": digest == FROZEN_SHA256,
        "bytes_match": len(data) == FROZEN_BYTES,
        "heading_has_k16876": "K16+876" in text,
        "has_25556": "255.56" in text,
        "has_00296": "0.0296" in text,
        "n_floor_anchor": len(floor),
        "n_portal_anchor": len(portal),
        "anchor_overlap": len(overlap),
        "anchors_disjoint": len(overlap) == 0,
        "boundary": count_boundary_cards(text),
        "initial_conditions": ic,
        "sigma_floor_writer_Pa": state["sigma_floor_Pa"],
        "sigma_floor_writer_fmt": f"{state['sigma_floor_Pa']:.6e}",
        "floor_ic_matches_writer": (
            sigma_line is not None
            and sigma_line["fields"][1].lower() == f"{state['sigma_floor_Pa']:.6e}".lower()
        ),
        "ccx_2_21_requires": list(CCX221_IC_FIELDS),
        "deck_ic_is_elset_uniaxial": ic.get("all_elset_uniaxial", False),
        "do_not_rewrite_inp": True,
    }


def portal_ledger_summary(ledger: dict) -> dict:
    stations = ledger.get("stations") or []
    by_span: dict[str, int] = {}
    rows = []
    for rec in stations:
        span = _span_of(float(rec["x"]))
        by_span[span] = by_span.get(span, 0) + 1
        rows.append(
            {
                "index": rec["index"],
                "x": rec["x"],
                "chainage": _chainage(rec["x"]),
                "span": span,
                "upstream": rec["upstream"],
                "downstream": rec["downstream"],
                "n_up_seg": rec["n_up_seg"],
                "n_dn_seg": rec["n_dn_seg"],
                "ok": rec["ok"],
            }
        )
    n_ok = sum(1 for r in rows if r["ok"] and r["upstream"] and r["downstream"])
    return {
        "expected_per_deck": N_PORTALS_PER_DECK,
        "expected_both_decks": N_PORTALS_BOTH_DECKS,
        "drawing_stations": len(PORTAL_X),
        "n_rows": len(rows),
        "n_ok_both_decks": n_ok * 2 if n_ok == len(rows) else n_ok,
        "upstream_hit": sum(1 for r in rows if r["upstream"]),
        "downstream_hit": sum(1 for r in rows if r["downstream"]),
        "both_decks_hit": sum(1 for r in rows if r["upstream"] and r["downstream"]) * 2,
        "n_missing": int(ledger.get("n_missing") or 0),
        "inserted_portals": int(ledger.get("inserted_portals") or 0),
        "by_span_stations": by_span,
        "pass_142": (
            len(rows) == N_PORTALS_PER_DECK
            and all(r["ok"] for r in rows)
            and int(ledger.get("n_missing") or 0) == 0
            and int(ledger.get("inserted_portals") or 0) == 0
        ),
        "unit": "榀",
        "not_unit": "槬",
        "stations": rows,
    }


def passage_table() -> list[dict]:
    return [
        {
            "index": i + 1,
            "label": PASSAGE_LABELS[i],
            "x": x,
            "chainage": _chainage(x),
            "span": _span_of(float(x)),
        }
        for i, x in enumerate(PASSAGE_X)
    ]


def run_ccx_on_copy(inp_path: Path, work: Path, timeout_s: float = 120.0) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    job = work / "job"
    copied = Path(str(job) + ".inp")
    shutil.copy2(inp_path, copied)
    copy_hash = sha256_file(copied)
    ccx = shutil.which("ccx")
    record = {
        "executed_here": False,
        "ccx_binary": ccx,
        "work": str(work),
        "copy_sha256": copy_hash,
        "copy_matches_frozen": copy_hash == FROZEN_SHA256,
        "original_untouched": sha256_file(inp_path) == FROZEN_SHA256,
    }
    if not ccx:
        record["reason"] = "ccx binary not found"
        return record
    version = subprocess.run([ccx, "-v"], capture_output=True, text=True, check=False)
    record["version_stdout"] = (version.stdout or "").strip()
    record["version_stderr"] = (version.stderr or "").strip()
    t0 = time.perf_counter()
    proc = subprocess.run(
        [ccx, job.name],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_s,
    )
    elapsed = time.perf_counter() - t0
    record.update(
        {
            "executed_here": True,
            "exit_code": proc.returncode,
            "wall_s": elapsed,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    )
    for ext in (".frd", ".dat", ".sta", ".cvg", ".12d", ".equ"):
        p = Path(str(job) + ext)
        if not p.exists():
            record[f"has{ext}"] = False
            continue
        record[f"has{ext}"] = True
        record[f"{ext}_bytes"] = p.stat().st_size
        record[f"{ext}_text"] = p.read_text(errors="replace")[:4000]
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    record["mentions_E_FLOOR_ROPE"] = "E_FLOOR_ROPE" in combined or "E_FLOOR_ROPE" in (
        record.get(".sta_text") or ""
    )
    record["mentions_3_549611"] = bool(
        re.search(r"3\.549611", combined + (record.get(".sta_text") or ""), re.I)
    )
    record["mentions_equations"] = bool(re.search(r"equation", combined, re.I))
    record["parse_fail_ic"] = (
        proc.returncode != 0
        and ("INITIAL" in combined.upper() or "E_FLOOR_ROPE" in combined)
    )
    return record


def write_portal_markdown(summary: dict, out: Path) -> None:
    lines = [
        "# 142 榀门架逐站对账（不是槬）",
        "",
        f"单幅 {summary['expected_per_deck']} 站 × 两幅 = {summary['expected_both_decks']} 榀。",
        f"缺站 {summary['n_missing']}，插入 {summary['inserted_portals']}。单位必须写「榀」。",
        "",
        "| 序号 | x (m) | 桩号 | 跨段 | 上游 | 下游 | n_up | n_dn | ok |",
        "|---:|---:|:---|:---|:---:|:---:|---:|---:|:---:|",
    ]
    for r in summary["stations"]:
        lines.append(
            f"| {r['index']} | {r['x']:.1f} | {r['chainage']} | {r['span']} | "
            f"{'Y' if r['upstream'] else 'N'} | {'Y' if r['downstream'] else 'N'} | "
            f"{r['n_up_seg']} | {r['n_dn_seg']} | {'Y' if r['ok'] else 'N'} |"
        )
    out.write_text("\n".join(lines) + "\n")


def main() -> int:
    artifacts = ROOT / "artifacts"
    inp = artifacts / FROZEN_NAME
    before = sha256_file(inp)
    if before != FROZEN_SHA256:
        print("REFUSING: frozen deck hash is not 82548e6a…", file=sys.stderr)
        return 2
    deck = audit_frozen_inp(inp)
    ledger = json.loads((artifacts / "portal_142_ledger.json").read_text())
    portals = portal_ledger_summary(ledger)
    write_portal_markdown(portals, artifacts / "portal_142_table.md")
    work = Path("/tmp/ccx-82548e6a")
    if work.exists():
        shutil.rmtree(work)
    ccx_run = run_ccx_on_copy(inp, work)
    after = sha256_file(inp)
    given = {
        "source": "user-supplied catwalk solve on hash 82548e6a; this run only re-reads and may reproduce",
        "deck_sha256": FROZEN_SHA256,
        "hash_must_not_change": True,
        "failed_keyword": "*INITIAL CONDITIONS",
        "failed_row": "E_FLOOR_ROPE,3.549611E+08",
        "exit_code": 201,
        "has_frd": False,
        "dat_empty": True,
        "sta_cvg_header_only": True,
        "wall_clock": "<1 s",
        "equation_count": None,
        "diagnosis": (
            "This deck TYPE=STRESS is ELSET + uniaxial; "
            "CalculiX 2.21 requires element number + integration point + six stresses"
        ),
    }
    record = {
        "deck": deck,
        "portals_142": {
            k: v for k, v in portals.items() if k != "stations"
        },
        "portals_142_n_stations": len(portals["stations"]),
        "passages_21": {
            "expected": N_CROSS_PASSAGES,
            "n": len(passage_table()),
            "stations": passage_table(),
        },
        "given_ccx_run": given,
        "local_ccx_reproduction": ccx_run,
        "original_hash_before": before,
        "original_hash_after": after,
        "original_untouched": before == after == FROZEN_SHA256,
        "scientific_claim": (
            "hashed coordinate-gated deck exists; 21 passages and 142 榀 portals "
            "reconcile with zero insertions; floor/portal anchors are disjoint; "
            "ccx 2.21 parse of TYPE=STRESS fails on ELSET+uniaxial; no spectrum claimed"
        ),
    }
    write_json(artifacts / "ic_format_audit.json", deck)
    write_json(artifacts / "ccx_run_82548e6a.json", record)
    print(json.dumps({
        "hash_unchanged": record["original_untouched"],
        "ic_elset_uniaxial": deck["deck_ic_is_elset_uniaxial"],
        "portals_142_pass": portals["pass_142"],
        "ccx_exit": ccx_run.get("exit_code"),
        "ccx_wall_s": ccx_run.get("wall_s"),
    }, indent=2))
    return 0 if record["original_untouched"] and deck["deck_ic_is_elset_uniaxial"] and portals["pass_142"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
