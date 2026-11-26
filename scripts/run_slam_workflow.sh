#!/usr/bin/env bash
# New live SLAM -> save -> map-bound poses -> AMCL/Nav2 -> HRI -> live panel.
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
source /opt/ros/humble/setup.bash
source install/setup.bash
unset ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE ROBOT_NAMESPACE
export ROS_DOMAIN_ID=98 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
task_runtime="/tmp/tb4_cuoiky_runtime_${UID}"
mkdir -p "$task_runtime" log/slam_workflow results
if [[ -f "$task_runtime/runner.pid" ]] && kill -0 "$(cat "$task_runtime/runner.pid")" 2>/dev/null; then
    echo 'Một phiên mô phỏng đang chạy; dùng bash scripts/stop_sim.sh trước.' >&2;exit 1
fi
/usr/bin/python3 scripts/cleanup_sim_processes.py --preserve "$$"
cp config/cyclonedds_local.xml "$task_runtime/cyclonedds.xml"
export CYCLONEDDS_URI="file://$task_runtime/cyclonedds.xml"
export IGN_PARTITION=tb4_cuoiky_lab_slam_98
echo "$IGN_PARTITION" > "$task_runtime/current_partition"
export ROS_LOG_DIR="$task_root/log/slam_workflow/ros"
export HF_HOME="$task_root/.cache-voice/huggingface"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LP_NUM_THREADS=2
task_folder="$task_root/maps/slam_runs/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$task_folder"
echo "$task_folder" > results/latest_slam_run.txt
echo "$$" > "$task_runtime/runner.pid"
task_sim='' task_slam='' task_nav='' task_rviz='' task_panel='' task_camera=''
stop_group() {
    local task_pid="$1"
    [[ -n "$task_pid" ]] || return 0
    kill -INT -- "-$task_pid" 2>/dev/null || true
    for task_i in {1..40};do kill -0 -- "-$task_pid" 2>/dev/null || break;sleep .1;done
    kill -TERM -- "-$task_pid" 2>/dev/null || true
    for task_i in {1..20};do kill -0 -- "-$task_pid" 2>/dev/null || break;sleep .1;done
    kill -KILL -- "-$task_pid" 2>/dev/null || true
    wait "$task_pid" 2>/dev/null || true
}
cleanup() {
    trap - EXIT INT TERM
    for task_pid in "$task_camera" "$task_panel" "$task_rviz";do
        if [[ -n "$task_pid" ]];then kill -TERM "$task_pid" 2>/dev/null || true;fi
    done
    stop_group "$task_nav";stop_group "$task_slam";stop_group "$task_sim"
    rm -f "$task_runtime/runner.pid" "$task_runtime/current_partition"
}
trap cleanup EXIT INT TERM
setsid ros2 launch tb4_cuoiky lab_world_sim.launch.py > log/slam_workflow/world.log 2>&1 &
task_sim="$!"
setsid ros2 launch turtlebot4_navigation slam.launch.py use_sim_time:=true sync:=false \
    params:="$task_root/config/slam.yaml" > log/slam_workflow/slam.log 2>&1 &
task_slam="$!"
LIBGL_ALWAYS_SOFTWARE=1 rviz2 -d config/nav_voice.rviz --ros-args -p use_sim_time:=true > log/slam_workflow/rviz.log 2>&1 &
task_rviz="$!"
echo 'B1: đang quét SLAM mới bằng LiDAR; không nạp bản đồ tham chiếu.'
/usr/bin/python3 scripts/slam_scan_lab.py --output "$task_folder" 2>&1 | tee log/slam_workflow/mapping.log
echo 'Đã lưu map và ba địa điểm. Đang chuyển từ SLAM sang AMCL/Nav2...'
stop_group "$task_slam";task_slam=''
setsid ros2 launch tb4_cuoiky lab_navigation.launch.py catalog:="$task_folder/destinations.yaml" \
    use_sim_time:=true start_rviz:=false nav_params:="$task_root/config/nav2.yaml" \
    localization_params:="$task_root/config/localization.yaml" \
    > log/slam_workflow/navigation.log 2>&1 &
task_nav="$!"
/usr/bin/python3 scripts/lab_sim_ready.py --folder "$task_folder"
/usr/bin/python3 tests/slam_hri_navigation.py --folder "$task_folder" 2>&1 | tee log/slam_workflow/navigation_test.log
/usr/bin/python3 scripts/hri_panel.py > log/slam_workflow/panel.log 2>&1 &
task_panel="$!"
if [[ -f .venv-gesture/bin/python && -f models/gesture_recognizer.task ]];then
    .venv-gesture/bin/python scripts/gesture_recognition_node.py --ros-args \
        -p model_path:="$task_root/models/gesture_recognizer.task" -p camera_index:=0 -p hri_mode:=true \
        > log/slam_workflow/camera.log 2>&1 &
    task_camera="$!"
fi
echo 'SẴN SÀNG: micro tự nghe liên tục. Nói tên bàn hoặc giơ cử chỉ để chạy ngay; chỉ xác nhận khi lưu map hoặc địa điểm.'
echo "Map và kết quả: $task_folder"
wait "$task_sim"
