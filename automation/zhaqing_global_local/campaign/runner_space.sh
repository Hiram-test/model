#!/usr/bin/env bash # Prepare only an ephemeral GitHub-hosted runner for large full-field data artifacts.
set -euo pipefail # Stop on unexpected preparation failures instead of hiding a storage problem.
if [[ "${RUNNER_ENVIRONMENT:-}" == "github-hosted" ]]; then # Protect local and user-managed self-hosted machines from cleanup.
  sudo rm -rf /usr/local/lib/android /usr/share/dotnet /opt/ghc /opt/hostedtoolcache/CodeQL # Remove only unrelated preinstalled hosted-runner toolchains.
fi # Keep every repository, model, artifact and native result intact.
df -h . # Report actual free capacity before downloading complete supervised histories.
