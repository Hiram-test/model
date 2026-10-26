#!/usr/bin/env bash
set -euo pipefail # Stop if source mesh, native renderer or screenshot creation fails.
cd "$(dirname "$0")/../.." # Resolve the repository root independently of the caller directory.
runtime_root="${PLOT_RUNTIME_ROOT:-/workspace/scratch/500ec816102b/plot-runtime}" # Allow relocation of the pinned native rendering tools.
output_dir="results/zhaqing_global_local_20261026/local" # Keep images and logs beside the actual mesh evidence.
mkdir -p "$output_dir" # Ensure the output destination exists.
rm -f "$output_dir/explicit_wires_mesh.png" "$output_dir/wires_only_mesh.png" # Remove only this renderer's previous outputs so a failed run cannot pass using stale images.
sed 's/ #.*$//' automation/zhaqing_global_local/render_local_mesh.fbl > "$output_dir/mesh_runtime.fbl" # Strip commentary because CGX treats trailing words as command arguments.
export LD_LIBRARY_PATH="$runtime_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" # Load the native CGX/Xvfb dependency closure.
display_number=$((1000 + $$ % 10000)) # Avoid stale X locks shared by isolated execution namespaces.
"$runtime_root/usr/bin/Xvfb" ":$display_number" -screen 0 2400x1600x24 -ac -nolisten unix -listen tcp > "$output_dir/mesh_xvfb.log" 2>&1 & # Open a private native graphics display in this process namespace.
display_pid=$! # Retain the exact display process for cleanup.
trap 'kill "$display_pid" 2>/dev/null || true; wait "$display_pid" 2>/dev/null || true' EXIT # Reap this renderer display so its own lock can be removed.
sleep 1 # Allow the display server to initialize before native rendering.
DISPLAY="127.0.0.1:$display_number" timeout 120 "$runtime_root/usr/bin/cgx" -b "$output_dir/mesh_runtime.fbl" > "$output_dir/mesh_cgx.log" 2>&1 # Render through CGX rather than a Python plotting library.
test -s "$output_dir/explicit_wires_mesh.png" # Require an actual nonempty native screenshot.
