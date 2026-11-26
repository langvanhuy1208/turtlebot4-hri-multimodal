#!/usr/bin/env bash
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
task_catalog="${1:?Usage: bash scripts/start_saved_map.sh /absolute/path/destinations.yaml}"
bash scripts/resume_lab.sh "$(dirname -- "$task_catalog")"
