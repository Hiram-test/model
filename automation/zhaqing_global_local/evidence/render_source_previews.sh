#!/usr/bin/env bash
set -euo pipefail # Stop if native conversion or rasterization fails.
: "${DWG2SVG:?Set DWG2SVG to the LibreDWG 0.13.3 native executable}" # Require a known source converter.
: "${RSVG_CONVERT:?Set RSVG_CONVERT to the librsvg 2.58 native executable}" # Require a native SVG rasterizer.
repo_root="${1:?Repository root is required}" # Resolve the authoritative drawing root explicitly.
preview_output="${2:?Output directory is required}" # Keep all generated outputs together.
mkdir -p "$preview_output" # Preserve native SVG bytes and render logs.
for key in saddle section deck general girder crossbeams; do # Render original source drawings used in the geometry review.
    case "$key" in # Bind each viewport to that source's native drawing extents.
        saddle) filename='29-索鞍构造.dwg'; viewport='0 0 840 594'; stroke='0.35'; width=2400; height=1697 ;; # Preserve the genuine Zhaqing saddle sheet.
        section) filename='桥跨横断面图.dwg'; viewport='0 0 840 594'; stroke='0.35'; width=2400; height=1697 ;; # Retain the disputed section reference for review.
        deck) filename='04-05-桥面板构造.dwg'; viewport='0 0 921.162247 297'; stroke='0.20'; width=3685; height=1188 ;; # Render both authentic steel-panel sheets.
        general) filename='01-扎青桥总体布置1.dwg'; viewport='0 0 154 55.4'; stroke='0.035'; width=3080; height=1108 ;; # Render the actual station and support layout.
        girder) filename='12-纵梁构造.dwg'; viewport='0 0 4200 2970'; stroke='0.8'; width=2800; height=1980 ;; # Render the actual3000/2700/2696girder connection geometry.
        crossbeams) filename='06-11-横梁构造.dwg'; viewport='0 0 13670.400521 6672.576365'; stroke='1.8'; width=4101; height=2002 ;; # Render all six crossbeam sheets with box and support-angle details.
    esac # Finish native-sheet viewport selection.
    source_file="$repo_root/source-inputs/zhaqing-suspension-bridge/drawings/$filename" # Resolve the unchanged repository source drawing.
    "$DWG2SVG" --mspace "$source_file" > "$preview_output/$key-native.svg" 2> "$preview_output/$key-native.log" # Convert actual native CAD entities without Python plotting.
    sed -E "s/stroke-width:0\\.0px/stroke-width:${stroke}px/g; s/viewBox=\"[^\"]*\"/viewBox=\"$viewport\"/; s/stroke:black/stroke:#ced8dc/g; s/fill=\"black\"/fill=\"#ced8dc\"/g" "$preview_output/$key-native.svg" > "$preview_output/$key-preview.svg" # Correct invisible strokes and shifted viewport while leaving all geometry coordinates unchanged.
    "$RSVG_CONVERT" -w "$width" -h "$height" -b '#101820' -o "$preview_output/$key-preview.png" "$preview_output/$key-preview.svg" # Rasterize exact source linework with the configured font environment.
done # Finish source previews without synthesizing dimensions or shapes.
