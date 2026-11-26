#!/usr/bin/env bash
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export CUOIKY_SCENE=maze
exec bash scripts/resume_lab.sh "$task_root/maps/maze"
