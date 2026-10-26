#!/usr/bin/env bash
set -euo pipefail # Fail before any later CFD stage can hide an earlier error.
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)" # Locate the versioned source rather than relying on cwd.
cfd_runtime="${CFD_RUNTIME:?Set CFD_RUNTIME to the extracted OpenFOAM/Gmsh dependency prefix}" # Require the chosen runtime explicitly.
case_dir="${1:?Pass the generated native CFD case directory}" # Run only the requested case.
g++ -std=c++17 -shared -fPIC "$script_dir/sha1_stream_compat.cpp" -ldl -o "$cfd_runtime/libsha1_stream_compat.so" # Repair only the known legacy SHA1 stream I/O incompatibility.
export PATH="$cfd_runtime/usr/bin:$PATH" # Prefer the declared native binaries.
export LD_LIBRARY_PATH="$cfd_runtime/usr/lib:$cfd_runtime/usr/lib/x86_64-linux-gnu:$cfd_runtime/usr/lib/x86_64-linux-gnu/openmpi/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" # Resolve the extracted solver dependencies.
export WM_PROJECT_DIR="$cfd_runtime/usr/share/openfoam" # Locate OpenFOAM1912 dictionaries.
export WM_PROJECT_VERSION=v1912 # Identify the solver release explicitly.
export FOAM_ETC="$WM_PROJECT_DIR/etc" # Provide the native OpenFOAM configuration directory.
export LD_PRELOAD="$cfd_runtime/libsha1_stream_compat.so${LD_PRELOAD:+:$LD_PRELOAD}" # Apply the narrowly typed SHA1 stream compatibility fix.
exec "$case_dir/Allrun" # Execute native mesh, verification and finite-volume solve stages.
