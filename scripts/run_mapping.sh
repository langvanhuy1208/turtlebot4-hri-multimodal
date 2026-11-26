#!/usr/bin/env bash
# Fresh SLAM with operator-selectable frontier exploration/manual control.
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
source scripts/sim_env.sh
export IGN_PARTITION=tb4_cuoiky_lab_slam_98
task_runtime="/tmp/tb4_cuoiky_runtime_${UID}"
mkdir -p "$task_runtime" log/mapping
if [[ -f "$task_runtime/runner.pid" ]] && kill -0 "$(cat "$task_runtime/runner.pid")" 2>/dev/null; then
 echo 'Đang có phiên mô phỏng. Chạy bash scripts/stop_sim.sh trước.';exit 1
fi
python3 scripts/cleanup_sim_processes.py --preserve "$$"
cp config/cyclonedds_local.xml "$task_runtime/cyclonedds.xml"
echo "$$" > "$task_runtime/runner.pid"
echo "$IGN_PARTITION" > "$task_runtime/current_partition"
task_pids=()
cleanup() {
 trap - EXIT INT TERM
 for task_pid in "${task_pids[@]}";do kill -INT -- "-$task_pid" 2>/dev/null || true;done
 sleep 1
 for task_pid in "${task_pids[@]}";do kill -TERM -- "-$task_pid" 2>/dev/null || true;done
 rm -f "$task_runtime/runner.pid" "$task_runtime/current_partition"
}
trap cleanup EXIT INT TERM
start_group() { setsid "$@" > "log/mapping/process_${#task_pids[@]}.log" 2>&1 & task_pids+=("$!"); }
start_group ros2 launch tb4_cuoiky lab_world_sim.launch.py
start_group ros2 launch turtlebot4_navigation slam.launch.py use_sim_time:=true sync:=false params:="$task_root/config/slam.yaml"
start_group ros2 launch tb4_cuoiky guarded_navigation.launch.py use_sim_time:=true params_file:="$task_root/config/nav2.yaml"
start_group ros2 run tb4_cuoiky frontier_explorer.py --ros-args -p use_sim_time:=true
# Wait for live SLAM and save a bootstrap catalog; this file is never a reference map.
python3 scripts/mapping_ready.py --folder "$task_runtime/mapping_session"
start_group ros2 run tb4_cuoiky lab_hri_node.py --ros-args -p use_sim_time:=true -p mapping_session:=true \
 -p regions_file:="$task_runtime/mapping_session/destinations.yaml" -r /voice_command:=/hri/voice -r /voice_nav/status:=/hri/status
start_group ros2 run tb4_cuoiky feedback_node.py
if [[ "${CUOIKY_HEADLESS:-false}" != true ]];then
 start_group env LIBGL_ALWAYS_SOFTWARE=1 rviz2 -d config/nav_voice.rviz --ros-args -p use_sim_time:=true
 start_group /usr/bin/python3 scripts/hri_panel.py
 start_group .venv-gesture/bin/python scripts/gesture_recognition_node.py --ros-args -p model_path:="$task_root/models/gesture_recognizer.task" -p camera_index:=0 -p hri_mode:=true
fi
ros2 topic pub --once /mapping/control std_msgs/msg/String "{data: '${1:-manual}'}"
echo 'READY: nói Robot tự động quét / Robot điều khiển thủ công / Robot dừng quét.'
echo 'Dừng quét trước khi nói Lưu bản đồ <tên>, rồi ngón cái hoặc Xác nhận.'
echo 'Terminal khác: source scripts/sim_env.sh; python3 scripts/lab_teleop.py --topic /cmd_vel_manual'
wait "${task_pids[0]}"
