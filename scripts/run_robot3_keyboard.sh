#!/usr/bin/env bash
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
source scripts/robot3_env.sh
mkdir -p log/robot3_keyboard
export ROS_LOG_DIR="$task_root/log/robot3_keyboard/ros"
/usr/bin/python3 scripts/robot3_keyboard_panel.py
