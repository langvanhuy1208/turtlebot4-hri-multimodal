#!/usr/bin/env bash
# Existing Wi-Fi/DDS discovery must already be configured; does not move the robot by itself.
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
source /opt/ros/humble/setup.bash
source install/setup.bash
task_profile="${1:?Usage: bash scripts/run_robot_hri.sh profile.yaml destinations.yaml}"
task_catalog="${2:?A map catalog made on the REAL environment is required}"
if [[ "${ROS_DOMAIN_ID:-0}" == 98 ]];then echo 'Đang dùng domain mô phỏng. Mở terminal đã cấu hình DDS robot thật.';exit 2;fi
export HF_HOME="$task_root/.cache-voice/huggingface"
ros2 launch tb4_cuoiky project_profile.launch.py profile:="$task_profile" catalog:="$task_catalog"
