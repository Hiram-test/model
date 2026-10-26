"""Extract traceable source entities; this program never renders graphics.""" # Keep source extraction separate from native graphics.
from __future__ import annotations # Permit stable modern annotation syntax.
import argparse # Read explicit source and output paths.
import hashlib # Bind evidence to exact original bytes.
import json # Store machine-readable audit evidence.
from pathlib import Path # Resolve portable repository paths.
import ezdxf # Read genuine LibreDWG-converted entity data.
DRAWINGS = {"saddle": "29-索鞍构造.dwg", "cables": "03-缆索布置.dwg", "section": "桥跨横断面图.dwg", "crossbeams": "06-11-横梁构造.dwg", "deck": "04-05-桥面板构造.dwg", "general": "01-扎青桥总体布置1.dwg", "girder": "12-纵梁构造.dwg"} # Freeze the inspected drawing inventory.
def digest(path: Path) -> str: # Hash exact file contents for reproducibility.
    return hashlib.sha256(path.read_bytes()).hexdigest() # Return the unmodified source hash.
def extract(path: Path) -> dict: # Extract raw dimensional and geometrical controls.
    doc = ezdxf.readfile(path) # Preserve CAD entity handles in the converted source.
    rows = [] # Accumulate source entities without inventing geometry.
    for entity in doc.modelspace(): # Visit actual model-space source objects.
        kind = entity.dxftype() # Retain original entity classification.
        if kind not in {"TEXT", "MTEXT", "DIMENSION", "ARC", "CIRCLE", "LINE", "LWPOLYLINE"}: # Limit extraction to interpretable evidence.
            continue # Leave unsupported source entities in the preserved DXF.
        row = {"handle": entity.dxf.handle, "type": kind, "layer": entity.dxf.layer} # Preserve source identity.
        if kind in {"TEXT", "MTEXT"}: # Preserve visible and empty text separately.
            row.update(text=entity.dxf.text if kind == "TEXT" else entity.plain_text(), insert=list(entity.dxf.insert)) # Read text without OCR or rewriting.
        elif kind in {"ARC", "CIRCLE"}: # Preserve true geometric circle and arc parameters.
            row.update(center=list(entity.dxf.center), radius=entity.dxf.radius) # Store raw drawing units.
            if kind == "ARC": # Arc angles are meaningful only for partial circles.
                row.update(start_angle_deg=entity.dxf.start_angle, end_angle_deg=entity.dxf.end_angle) # Preserve oriented source angles.
        elif kind == "LINE": # Preserve source endpoints for dimension closure.
            row.update(start=list(entity.dxf.start), end=list(entity.dxf.end)) # Store original source coordinates.
        elif kind == "LWPOLYLINE": # Preserve source vertices and bulges for later tracing.
            row.update(vertices=[list(point) for point in entity.get_points()], closed=entity.closed) # Avoid tessellating or approximating the source.
        elif kind == "DIMENSION": # Preserve numerical overrides without treating them as measured lengths.
            row.update(attributes=entity.dxf.all_existing_dxf_attribs()) # Keep dimensions, references, and style information.
        rows.append(row) # Retain every selected source object.
    return {"entity_count": len(doc.modelspace()), "units_header": doc.header.get("$INSUNITS"), "entities": rows} # Do not assign physical units from a potentially unset header.
def main() -> None: # Provide a reproducible non-rendering audit entry point.
    parser = argparse.ArgumentParser(description=__doc__) # Explain the scope of this evidence extractor.
    parser.add_argument("--source-dir", type=Path, required=True) # Require explicit original DWG location.
    parser.add_argument("--converted-dir", type=Path, required=True) # Require actual converter output.
    parser.add_argument("--output", type=Path, required=True) # Keep output under the requested result directory.
    args = parser.parse_args() # Read the user's or pipeline's explicit paths.
    args.output.mkdir(parents=True, exist_ok=True) # Preserve reproducible audit outputs.
    manifest = {"schema": "zhaqing-drawing-source-audit-v1", "graphics": "None; previews use native LibreDWG and librsvg", "drawings": {}, "engineering_release": "BLOCKED"} # Never infer design approval from extraction.
    for key, filename in DRAWINGS.items(): # Audit every declared source consistently.
        original = args.source_dir / filename # Resolve the repository's authoritative source.
        converted = args.converted_dir / (key + ".dxf") # Resolve the native conversion used for extraction.
        data = extract(converted) # Extract raw source entities with handles.
        evidence_path = args.output / (key + "_entities.json") # Use stable per-drawing evidence names.
        evidence_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8") # Retain human-readable source evidence.
        manifest["drawings"][key] = {"source": filename, "source_sha256": digest(original), "dxf_sha256": digest(converted), "entity_count": data["entity_count"], "entities_file": evidence_path.name} # Bind each extracted object inventory to exact source bytes.
    cable = extract(args.converted_dir / "cables.dxf") # Recheck the actual cable note directly.
    cable_note = next(row for row in cable["entities"] if row["handle"] == "16B5") # Require the known original source handle.
    assert "283" in cable_note["text"] and "^5" in cable_note["text"] and "1670" in cable_note["text"], cable_note # Fail if the source facts no longer match.
    manifest["verified_wire_note"] = cable_note # Retain exact wording supporting 283 wires of 5 mm.
    section = extract(args.converted_dir / "section.dxf") # Audit the previously assumed section drawing identity.
    section_title = next(row for row in section["entities"] if row["handle"] == "C2A") # Preserve the conflicting titleblock source.
    saddle = extract(args.converted_dir / "saddle.dxf") # Compare against a genuine Zhaqing component drawing.
    saddle_title = next(row for row in saddle["entities"] if row["handle"] == "4D76") # Preserve the correct bridge project name.
    manifest["section_project_identity"] = {"status": "CONFLICT_UNRESOLVED", "section_title": section_title, "zhaqing_title": saddle_title, "consequence": "Do not certify the standalone section drawing as the Zhaqing aerodynamic section; reconstruct using the matching project drawings or obtain association evidence."} # Expose a material source conflict rather than silently accepting it.
    manifest["conversion_limitations"] = ["LibreDWG 0.13.3 reports missing-handle warnings; original DWGs remain authoritative.", "Source MTEXT contains empty entities and native SVG ignores MTEXT; previews are linework evidence, not a complete dimension transcription.", "Saddle wire packing, weld fatigue properties, and as-built contact conditions are not fixed by the extracted cable-count note."] # State the precise limits of this audit.
    (args.output / "drawing_source_audit.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8") # Write the traceable audit receipt.
    print(json.dumps({"status": "SOURCE_EXTRACTED_WITH_IDENTITY_CONFLICT", "drawings": len(DRAWINGS), "wire_count": 283, "wire_diameter_mm": 5}, ensure_ascii=False)) # Report extraction without claiming engineering validation.
if __name__ == "__main__": # Run only when explicitly invoked.
    main() # Execute the source extraction audit.
