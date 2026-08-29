from __future__ import annotations  # Enable modern annotation behavior.
import csv  # Read the frozen coordinate table.
import json  # Read configuration and write manifests.
from pathlib import Path  # Build portable repository paths.

ROOT = Path(__file__).resolve().parents[1]  # Resolve the trial package root.
CONFIG_PATH = ROOT / "config" / "trial_config.json"  # Point to the frozen trial configuration.
NODE_PATH = ROOT / "ir" / "target_reference_nodes.csv"  # Point to the frozen target/reference coordinates.
OUT_DIR = ROOT / "solver" / "drafts"  # Keep unverified decks in the draft solver directory.


def load_json(path: Path) -> dict:  # Load one UTF-8 JSON object.
    return json.loads(path.read_text(encoding="utf-8"))  # Parse and return the object.


def load_rows(path: Path) -> list[dict]:  # Load all coordinate records in deterministic order.
    with path.open("r", encoding="utf-8", newline="") as handle:  # Open the CSV without newline ambiguity.
        return list(csv.DictReader(handle))  # Return every row as a dictionary.


def emit(lines: list[str], explanation: str, active_line: str) -> None:  # Append one explained CalculiX line.
    lines.append(f"** {explanation}")  # Place a safe comment immediately before the active line.
    lines.append(active_line)  # Append the active solver line.


def deck_nodes(rows: list[dict]) -> list[str]:  # Build the reference-geometry node block.
    lines: list[str] = []  # Create a local line buffer.
    emit(lines, "Begin nodes for the current zero-stress reference geometry guess.", "*NODE, NSET=ALL_NODES")  # Open the node block.
    for row in rows:  # Preserve the frozen coordinate-table order.
        emit(lines, f"Define reference node {row['node_id']}.", f"{int(row['node_id'])}, {float(row['x_m']):.9f}, {float(row['y_m']):.9f}, {float(row['z_reference_m']):.9f}")  # Write one node.
    return lines  # Return the complete node block.


def deck_elements(rows: list[dict]) -> list[str]:  # Build both cable lines and smoke-only cross ties.
    lines: list[str] = []  # Create a local line buffer.
    deck_nodes_by_id = {"DECK-P": [], "DECK-M": []}  # Collect ordered nodes for both catwalk lines.
    station_nodes: dict[int, dict[str, int]] = {}  # Collect paired nodes at every station.
    for row in rows:  # Traverse each frozen coordinate record.
        deck_id = row["deck_id"]  # Read the stable deck identifier.
        node_id = int(row["node_id"])  # Convert the node identifier to an integer.
        station = int(row["station_index"])  # Convert the station index to an integer.
        deck_nodes_by_id[deck_id].append(node_id)  # Append the node to its deck line.
        station_nodes.setdefault(station, {})[deck_id] = node_id  # Register the paired station node.
    emit(lines, "Begin positive-y equivalent floor-rope elements.", "*ELEMENT, TYPE=T3D2, ELSET=DECK_P")  # Open the positive-y cable block.
    for index, pair in enumerate(zip(deck_nodes_by_id["DECK-P"][:-1], deck_nodes_by_id["DECK-P"][1:]), start=1):  # Connect adjacent positive-y stations.
        emit(lines, f"Connect positive-y nodes {pair[0]} and {pair[1]}.", f"{11000 + index}, {pair[0]}, {pair[1]}")  # Write one cable element.
    emit(lines, "Begin negative-y equivalent floor-rope elements.", "*ELEMENT, TYPE=T3D2, ELSET=DECK_M")  # Open the negative-y cable block.
    for index, pair in enumerate(zip(deck_nodes_by_id["DECK-M"][:-1], deck_nodes_by_id["DECK-M"][1:]), start=1):  # Connect adjacent negative-y stations.
        emit(lines, f"Connect negative-y nodes {pair[0]} and {pair[1]}.", f"{12000 + index}, {pair[0]}, {pair[1]}")  # Write one cable element.
    emit(lines, "Begin axial ties used only to smoke-test two-deck connectivity.", "*ELEMENT, TYPE=T3D2, ELSET=SMOKE_TIES")  # Open the tie block.
    for station in sorted(station_nodes):  # Connect both deck lines at every smoke station.
        node_p = station_nodes[station]["DECK-P"]  # Read the positive-y node.
        node_m = station_nodes[station]["DECK-M"]  # Read the negative-y node.
        emit(lines, f"Connect both deck lines at smoke station {station}; this is not a production portal or passage.", f"{13001 + station}, {node_p}, {node_m}")  # Write one smoke tie.
    return lines  # Return the complete element block.


def deck_properties(config: dict) -> list[str]:  # Build smoke-only material and section definitions.
    lines: list[str] = []  # Create a local line buffer.
    model = config["smokeModel"]  # Read the frozen smoke-model properties.
    emit(lines, "Define the equivalent floor-rope material.", "*MATERIAL, NAME=MAT_FLOOR_EQ")  # Open the cable material.
    emit(lines, "Define cable-group elasticity.", "*ELASTIC")  # Open the elastic block.
    emit(lines, "Write rope-group elastic modulus and Poisson ratio.", f"{model['ropeElasticModulus_Pa']:.9e}, {model['ropePoisson']:.9f}")  # Write cable elasticity.
    emit(lines, "Define smoke-only effective density that reproduces the registered line load.", "*DENSITY")  # Open the density block.
    emit(lines, "Write effective density without adding any second self-weight source.", f"{model['effectiveDensity_kg_per_m3']:.12e}")  # Write cable density.
    emit(lines, "Assign the total area of sixteen floor ropes to the positive-y equivalent line.", "*SOLID SECTION, ELSET=DECK_P, MATERIAL=MAT_FLOOR_EQ")  # Open the first cable section.
    emit(lines, "Write the equivalent positive-y cable area.", f"{model['floorRopeEquivalentArea_m2_perDeck']:.12e}")  # Write the first area.
    emit(lines, "Assign the same total area to the negative-y equivalent line.", "*SOLID SECTION, ELSET=DECK_M, MATERIAL=MAT_FLOOR_EQ")  # Open the second cable section.
    emit(lines, "Write the equivalent negative-y cable area.", f"{model['floorRopeEquivalentArea_m2_perDeck']:.12e}")  # Write the second area.
    emit(lines, "Define a massless smoke-tie material.", "*MATERIAL, NAME=MAT_TIE_SMOKE")  # Open the tie material.
    emit(lines, "Define smoke-tie elasticity.", "*ELASTIC")  # Open the tie elastic block.
    emit(lines, "Write smoke-tie elastic constants.", "2.060000000e11, 0.300000000")  # Write tie elasticity.
    emit(lines, "Assign the smoke-only axial area to transverse ties.", "*SOLID SECTION, ELSET=SMOKE_TIES, MATERIAL=MAT_TIE_SMOKE")  # Open the tie section.
    emit(lines, "Write the smoke-tie area.", f"{model['crossTieArea_m2']:.12e}")  # Write the tie area.
    return lines  # Return the complete property block.


def support_ids(rows: list[dict]) -> list[int]:  # Identify both ends of both smoke cable lines.
    return [int(row["node_id"]) for row in rows if int(row["is_support"]) == 1]  # Return the four physical support nodes.


def internal_rows(rows: list[dict]) -> list[dict]:  # Identify temporary erection-control nodes.
    return [row for row in rows if int(row["is_support"]) == 0]  # Exclude the four physical supports.


def add_supports(lines: list[str], supports: list[int], reset: bool) -> None:  # Add only physical end supports.
    keyword = "*BOUNDARY, OP=NEW" if reset else "*BOUNDARY"  # Reset temporary controls only during release.
    emit(lines, "Open the physical support block.", keyword)  # Open the boundary block.
    for node_id in supports:  # Constrain each physical end node.
        emit(lines, f"Fix all translations at physical support node {node_id}.", f"{node_id}, 1, 3, 0.0")  # Write one support record.


def zeroform_deck(config: dict, rows: list[dict]) -> list[str]:  # Build the complete reduced zero-stress inverse-form smoke deck.
    lines: list[str] = []  # Create the output line buffer.
    emit(lines, "Open the unverified smoke-deck heading.", "*HEADING")  # Open the heading.
    emit(lines, "Write the stable deck identity.", "CW-CCX-ZF-SMK-20260829-01 ZERO-STRESS INVERSE FORM-FINDING SMOKE")  # Write the title.
    lines.append("** PRESTRESS_POLICY=ZERO_IMPORTED_PRESTRESS")  # Record the hard no-imported-prestress policy.
    lines.extend(deck_nodes(rows))  # Append reference nodes.
    lines.extend(deck_elements(rows))  # Append cable and tie elements.
    lines.extend(deck_properties(config))  # Append material and section properties.
    supports = support_ids(rows)  # Resolve physical support nodes.
    emit(lines, "Start displacement-controlled erection with geometric nonlinearity.", "*STEP, NAME=ZF_S1_ERECTION, NLGEOM")  # Open erection step.
    emit(lines, "Select static continuation for erection.", "*STATIC")  # Open static controls.
    emit(lines, "Write erection increment controls.", "0.01, 1.0, 1.0e-8, 0.05")  # Write erection increments.
    add_supports(lines, supports, reset=False)  # Add physical supports.
    emit(lines, "Open temporary internal controls that regularize the erection path only.", "*BOUNDARY")  # Open temporary boundary controls.
    for row in internal_rows(rows):  # Prescribe each internal smoke node during erection.
        node_id = int(row["node_id"])  # Read the stable node identifier.
        delta_z = float(row["z_target_m"]) - float(row["z_reference_m"])  # Compute the target-minus-reference vertical increment.
        emit(lines, f"Hold temporary erection node {node_id} in the longitudinal direction.", f"{node_id}, 1, 1, 0.0")  # Write temporary x control.
        emit(lines, f"Hold temporary erection node {node_id} in the transverse direction.", f"{node_id}, 2, 2, 0.0")  # Write temporary y control.
        emit(lines, f"Move temporary erection node {node_id} to the target vertical coordinate.", f"{node_id}, 3, 3, {delta_z:.12e}")  # Write temporary z control.
    emit(lines, "Request erection displacement and reaction fields.", "*NODE FILE")  # Open erection nodal output.
    emit(lines, "Write erection displacement and reaction fields.", "U, RF")  # Request erection nodal output.
    emit(lines, "Request erection stress and strain fields.", "*EL FILE")  # Open erection element output.
    emit(lines, "Write erection stress and strain fields.", "S, E")  # Request erection element output.
    emit(lines, "End the erection step.", "*END STEP")  # Close erection step.
    emit(lines, "Start dead-load release with geometric nonlinearity.", "*STEP, NAME=ZF_S2_DEADLOAD_RELEASE, NLGEOM")  # Open release step.
    emit(lines, "Select static continuation for release.", "*STATIC")  # Open release static controls.
    emit(lines, "Write conservative release increment controls.", "0.002, 1.0, 1.0e-9, 0.02")  # Write release increments.
    add_supports(lines, supports, reset=True)  # Remove temporary controls and retain physical supports only.
    gravity = config["smokeModel"]["equivalentDeadLoad_N_per_m_perDeck"] / config["smokeModel"]["equivalentMass_kg_per_m_perDeck"]  # Reconstruct gravity from the frozen load and mass ledger.
    emit(lines, "Replace prior distributed loads with the registered gravity field.", "*DLOAD, OP=NEW")  # Open release gravity loads.
    emit(lines, "Apply downward gravity to the positive-y cable line.", f"DECK_P, GRAV, {gravity:.12e}, 0.0, 0.0, -1.0")  # Write the first gravity load.
    emit(lines, "Apply downward gravity to the negative-y cable line.", f"DECK_M, GRAV, {gravity:.12e}, 0.0, 0.0, -1.0")  # Write the second gravity load.
    emit(lines, "Request loaded coordinates, displacements, and reactions for the inverse update.", "*NODE FILE")  # Open release nodal output.
    emit(lines, "Write loaded coordinates, displacements, and reactions.", "COORD, U, RF")  # Request release nodal output.
    emit(lines, "Request released cable stress and strain.", "*EL FILE")  # Open release element output.
    emit(lines, "Write released cable stress and strain.", "S, E")  # Request release element output.
    emit(lines, "End the dead-load release step.", "*END STEP")  # Close release step.
    emit(lines, "Start a no-added-load equilibrium hold step.", "*STEP, NAME=ZF_S3_HOLD, NLGEOM")  # Open hold step.
    emit(lines, "Select a bounded static hold interval.", "*STATIC")  # Open hold static controls.
    emit(lines, "Write hold increment controls.", "0.05, 1.0, 1.0e-9, 0.05")  # Write hold increments.
    emit(lines, "Reapply exactly the same gravity and add no new physical action.", "*DLOAD, OP=NEW")  # Open hold gravity loads.
    emit(lines, "Repeat downward gravity on the positive-y cable line.", f"DECK_P, GRAV, {gravity:.12e}, 0.0, 0.0, -1.0")  # Repeat first gravity load.
    emit(lines, "Repeat downward gravity on the negative-y cable line.", f"DECK_M, GRAV, {gravity:.12e}, 0.0, 0.0, -1.0")  # Repeat second gravity load.
    emit(lines, "Request hold coordinates, displacements, and reactions.", "*NODE FILE")  # Open hold nodal output.
    emit(lines, "Write hold coordinates, displacements, and reactions.", "COORD, U, RF")  # Request hold nodal output.
    emit(lines, "Request hold cable stress and strain.", "*EL FILE")  # Open hold element output.
    emit(lines, "Write hold cable stress and strain.", "S, E")  # Request hold element output.
    emit(lines, "End the no-added-load hold step.", "*END STEP")  # Close hold step.
    return lines  # Return the complete smoke deck.


def tangent_template() -> list[str]:  # Build the locked tangent-frequency template.
    return ["** DYNAMIC_GATE=NOT_ARMED", "** Include a regenerated accepted static base before this perturbation step.", "*INCLUDE, INPUT=CONVERGED_ZEROFORM_STATIC_BASE.inp", "** Start small-amplitude tangent modal extraction.", "*STEP, NAME=DX_TANGENT_MODAL, PERTURBATION", "** Request frequencies without target-frequency filtering.", "*FREQUENCY", "** Request the first twenty modes.", "20", "** Request modal displacements.", "*NODE FILE", "** Write modal displacements.", "U", "** End tangent modal extraction.", "*END STEP"]  # Return the locked template with every active line explained.


def zero_load_template() -> list[str]:  # Build the locked zero-added-load transient template.
    return ["** DYNAMIC_GATE=NOT_ARMED", "** Include a reproducible accepted static base before transient integration.", "*INCLUDE, INPUT=CONVERGED_ZEROFORM_STATIC_BASE.inp", "** Start a nonlinear transient with no new load.", "*STEP, NAME=DX_ZERO_LOAD_TRANSIENT, NLGEOM", "** Select implicit dynamic integration.", "*DYNAMIC", "** Use placeholder time controls pending a time-step study.", "0.05, 20.0", "** Request displacement and velocity histories.", "*NODE FILE", "** Write displacement and velocity histories.", "U, V", "** End zero-load transient.", "*END STEP"]  # Return the locked template with every active line explained.


def free_decay_template() -> list[str]:  # Build the locked finite-amplitude free-decay template.
    return ["** DYNAMIC_GATE=NOT_ARMED", "** Include a reproducible accepted static base before perturbation.", "*INCLUDE, INPUT=CONVERGED_ZEROFORM_STATIC_BASE.inp", "** Start a short static perturbation step.", "*STEP, NAME=DX_PERTURB, NLGEOM", "** Select static perturbation control.", "*STATIC", "** Use conservative placeholder increments.", "0.1, 1.0, 1.0e-8, 0.1", "** INSERT_MODE_SHAPED_OR_PAIRED_TWIST_DISPLACEMENT_HERE", "** End the perturbation step.", "*END STEP", "** Start nonlinear free decay after temporary controls are removed.", "*STEP, NAME=DX_FREE_DECAY, NLGEOM", "** Select implicit dynamic integration.", "*DYNAMIC", "** Use placeholder time controls pending sensitivity checks.", "0.02, 120.0", "** Request displacement, velocity, and acceleration histories.", "*NODE FILE", "** Write displacement, velocity, and acceleration histories.", "U, V, A", "** End free decay.", "*END STEP"]  # Return the locked template with every active line explained.


def write_deck(path: Path, lines: list[str]) -> None:  # Write one deterministic UTF-8 deck.
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")  # Preserve exact line order and one terminal newline.


def main() -> None:  # Regenerate all development decks and their manifest.
    config = load_json(CONFIG_PATH)  # Load the frozen configuration.
    rows = load_rows(NODE_PATH)  # Load target/reference node records.
    OUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the output directory exists.
    write_deck(OUT_DIR / "SMK-Z0-01_zero_stress_formfind.inp", zeroform_deck(config, rows))  # Write the reduced form-finding smoke deck.
    write_deck(OUT_DIR / "PILOT-DYN-01_tangent_frequency_template.inp", tangent_template())  # Write the locked tangent-frequency template.
    write_deck(OUT_DIR / "PILOT-DYN-02_zero_load_transient_template.inp", zero_load_template())  # Write the locked zero-load transient template.
    write_deck(OUT_DIR / "PILOT-DYN-03_free_decay_template.inp", free_decay_template())  # Write the locked free-decay template.
    manifest = {"generated": sorted(path.name for path in OUT_DIR.glob("*.inp")), "solverExecuted": False, "status": "DEVELOPMENT_DRAFTS_ONLY"}  # Build the generation manifest.
    (OUT_DIR / "generation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # Write the generation manifest.


if __name__ == "__main__":  # Execute regeneration only when called directly.
    main()  # Generate all draft decks.
