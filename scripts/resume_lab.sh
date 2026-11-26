#!/usr/bin/env bash
# Resume the saved SLAM map without rescanning; speech listens automatically.
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
source /opt/ros/humble/setup.bash
source install/setup.bash
unset ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE ROBOT_NAMESPACE
export ROS_DOMAIN_ID=98 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
case "${CUOIKY_SCENE:-lab}" in
 lab) task_world_launch=lab_world_sim.launch.py;task_rviz_config=config/nav_voice.rviz;export IGN_PARTITION=tb4_cuoiky_lab_slam_98;;
 maze) task_world_launch=maze_world_sim.launch.py;task_rviz_config=config/nav_maze.rviz;export IGN_PARTITION=tb4_cuoiky_maze_98;;
 *) echo 'CUOIKY_SCENE phải là lab hoặc maze';exit 2;;
esac
export HF_HOME="$task_root/.cache-voice/huggingface"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LP_NUM_THREADS=2
task_runtime="/tmp/tb4_cuoiky_runtime_${UID}"
mkdir -p "$task_runtime/resume" log/live_resume
if [[ -f "$task_runtime/runner.pid" ]] && kill -0 "$(cat "$task_runtime/runner.pid")" 2>/dev/null; then
    echo 'Một phiên đang chạy. Dừng bằng bash scripts/stop_sim.sh trước.';exit 1
fi
/usr/bin/python3 scripts/cleanup_sim_processes.py --preserve "$$"
cp config/cyclonedds_local.xml "$task_runtime/cyclonedds.xml"
export CYCLONEDDS_URI="file://$task_runtime/cyclonedds.xml"
export ROS_LOG_DIR="$task_root/log/live_resume/ros"
echo "$$" > "$task_runtime/runner.pid"
echo "$IGN_PARTITION" > "$task_runtime/current_partition"
task_map_folder="${1:-}"
if [[ -z "$task_map_folder" ]];then
 if [[ "${CUOIKY_SCENE:-lab}" == maze ]];then task_map_folder="$task_root/maps/maze"
 else read -r task_map_folder < results/latest_slam_run.txt;fi
fi
/usr/bin/python3 - "$task_map_folder" "$task_runtime/resume" <<'PY'
from pathlib import Path
import json,math,sys
folder=Path(sys.argv[1]);runtime=Path(sys.argv[2])
if (folder/'map_metadata.json').exists():
 pose=json.loads((folder/'map_metadata.json').read_text())['spawn_initial_pose']
else:
 report=json.loads((folder/'mapping_results.json').read_text())
 last=report['waypoints'][-1]['odom'];end=report['localization_initial_pose']
 yaw=end['yaw']-last[2]
 pose=dict(x=end['x']-math.cos(yaw)*last[0]+math.sin(yaw)*last[1],
           y=end['y']-math.sin(yaw)*last[0]-math.cos(yaw)*last[1],yaw=yaw)
(runtime/'initial_pose.json').write_text(json.dumps(pose)+'\n')
link=runtime/'destinations.yaml'
if link.is_symlink():link.unlink()
link.symlink_to(folder/'destinations.yaml')
PY
task_world='' task_nav='' task_rviz='' task_panel='' task_camera=''
stop_group() {
    local task_pid="$1"
    [[ -n "$task_pid" ]] || return 0
    kill -INT -- "-$task_pid" 2>/dev/null || true
    for task_i in {1..40};do kill -0 -- "-$task_pid" 2>/dev/null || break;sleep .1;done
    kill -TERM -- "-$task_pid" 2>/dev/null || true
    sleep .3
    kill -KILL -- "-$task_pid" 2>/dev/null || true
    wait "$task_pid" 2>/dev/null || true
}
cleanup() {
    trap - EXIT INT TERM
    for task_pid in "$task_panel" "$task_camera" "$task_rviz";do
        if [[ -n "$task_pid" ]];then kill -TERM "$task_pid" 2>/dev/null || true;fi
    done
    stop_group "$task_nav";stop_group "$task_world"
    rm -f "$task_runtime/runner.pid" "$task_runtime/current_partition"
}
trap cleanup EXIT INT TERM
setsid ros2 launch tb4_cuoiky "$task_world_launch" > log/live_resume/world.log 2>&1 &
task_world="$!"
setsid ros2 launch tb4_cuoiky lab_navigation.launch.py catalog:="$task_map_folder/destinations.yaml" \
    use_sim_time:=true start_rviz:=false nav_params:="$task_root/config/nav2.yaml" \
    localization_params:="$task_root/config/localization.yaml" \
    > log/live_resume/navigation.log 2>&1 &
task_nav="$!"
LIBGL_ALWAYS_SOFTWARE=1 rviz2 -d "$task_rviz_config" --ros-args -p use_sim_time:=true > log/live_resume/rviz.log 2>&1 &
task_rviz="$!"
/usr/bin/python3 scripts/lab_sim_ready.py --folder "$task_runtime/resume"
if [[ "${CUOIKY_AUTOTEST:-false}" == true ]]; then
    /usr/bin/python3 tests/direct_hri_navigation.py --catalog "$task_map_folder/destinations.yaml" \
        --output "$task_root/results/${CUOIKY_SCENE:-lab}_navigation_sim" > log/live_resume/direct_arrival_test.log 2>&1
fi
if [[ "${CUOIKY_HEADLESS:-false}" != true ]];then
/usr/bin/python3 scripts/hri_panel.py > log/live_resume/panel.log 2>&1 &
task_panel="$!"
.venv-gesture/bin/python scripts/gesture_recognition_node.py --ros-args \
    -p model_path:="$task_root/models/gesture_recognizer.task" -p camera_index:=0 -p hri_mode:=true \
    > log/live_resume/camera.log 2>&1 &
task_camera="$!"
fi
echo 'READY: nói trực tiếp; micro tự nghe, không cần bấm thu âm.'
wait "$task_world"
