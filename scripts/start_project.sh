#!/usr/bin/env bash
# One session: scan, confirmed save, localization, arbitrary places; no simulation on real robot.
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
task_mode="${1:-sim}"
if [[ $# -gt 0 ]];then shift;fi
source /opt/ros/humble/setup.bash
source install/setup.bash
export HF_HOME="$task_root/.cache-voice/huggingface"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LP_NUM_THREADS=2
export LIBGL_ALWAYS_SOFTWARE=1
if [[ "$task_mode" == sim ]];then
 unset ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE ROBOT_NAMESPACE
 export ROS_DOMAIN_ID=98 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
 export IGN_PARTITION=tb4_cuoiky_session_98
 task_runtime="/tmp/tb4_cuoiky_runtime_${UID}"
 mkdir -p "$task_runtime"
 cp config/cyclonedds_local.xml "$task_runtime/cyclonedds.xml"
 export CYCLONEDDS_URI="file://$task_runtime/cyclonedds.xml"
elif [[ "$task_mode" != robot ]];then
 echo 'Usage: bash scripts/start_project.sh [sim|robot] [--scene maze|lab] [--profile file] [--auto]';exit 2
fi
exec /usr/bin/python3 scripts/project_session.py "$task_mode" "$@"
