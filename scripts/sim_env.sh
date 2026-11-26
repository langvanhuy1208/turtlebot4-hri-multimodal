#!/usr/bin/env bash
# Source this file from a second terminal to talk to this simulation only.
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/humble/setup.bash
source "$task_root/install/setup.bash"
unset ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE ROBOT_NAMESPACE
export ROS_DOMAIN_ID=98 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file:///tmp/tb4_cuoiky_runtime_${UID}/cyclonedds.xml"
export IGN_PARTITION=tb4_cuoiky_sim_98
if [[ -f "/tmp/tb4_cuoiky_runtime_${UID}/current_partition" ]]; then
    read -r IGN_PARTITION < "/tmp/tb4_cuoiky_runtime_${UID}/current_partition"
    export IGN_PARTITION
fi
export ROS_LOG_DIR="$task_root/log/simulation/ros"
export HF_HOME="$task_root/.cache-voice/huggingface"
cd "$task_root"
