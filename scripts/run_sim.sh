#!/usr/bin/env bash
# Isolated local simulation. Never uses the domain configured for a real robot.
set -eo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
task_mode="${1:---demo}"
case "$task_mode" in --demo|--interactive|--test) ;; *) echo 'Usage: bash scripts/run_sim.sh [--demo|--interactive|--test]'; exit 2;; esac
source /opt/ros/humble/setup.bash
if [[ ! -f install/setup.bash ]]; then
    colcon build --packages-select tb4_cuoiky --symlink-install
fi
source install/setup.bash
export ROS_DOMAIN_ID=98
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
task_runtime="/tmp/tb4_cuoiky_runtime_${UID}"
mkdir -p "$task_runtime" "$task_root/log/simulation"
cp config/cyclonedds_local.xml "$task_runtime/cyclonedds.xml"
export CYCLONEDDS_URI="file://$task_runtime/cyclonedds.xml"
export IGN_PARTITION=tb4_cuoiky_sim_98
export ROS_LOG_DIR="$task_root/log/simulation/ros"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LP_NUM_THREADS=2
export HF_HOME="$task_root/.cache-voice/huggingface"
task_sim_pid='' task_panel_pid=''
cleanup() {
    trap - EXIT INT TERM
    if [[ -n "$task_panel_pid" ]]; then kill -TERM "$task_panel_pid" 2>/dev/null || true; fi
    if [[ -n "$task_sim_pid" ]]; then
        kill -INT -- "-$task_sim_pid" 2>/dev/null || true
        for task_attempt in {1..40}; do
            kill -0 "$task_sim_pid" 2>/dev/null || break
            sleep .1
        done
        kill -TERM -- "-$task_sim_pid" 2>/dev/null || true
        wait "$task_sim_pid" 2>/dev/null || true
    fi
    rm -f "$task_runtime/runner.pid"
}
if [[ -f "$task_runtime/runner.pid" ]] && kill -0 "$(cat "$task_runtime/runner.pid")" 2>/dev/null; then
    echo 'Một phiên cuoiky đang chạy. Dừng phiên đó trước.' >&2
    exit 1
fi
/usr/bin/python3 scripts/cleanup_sim_processes.py --preserve "$$"
echo "$$" > "$task_runtime/runner.pid"
trap cleanup EXIT INT TERM
task_rviz="${CUOIKY_RVIZ:-true}"
task_headless="${CUOIKY_HEADLESS:-true}"
setsid ros2 launch tb4_cuoiky cuoiky_sim.launch.py headless:="$task_headless" start_rviz:="$task_rviz" \
    > log/simulation/launch.log 2>&1 &
task_sim_pid="$!"
echo 'Đang mở Gazebo, Nav2 và RViz...'
/usr/bin/python3 scripts/voice_demo_ready.py --initialize-spawn --timeout 180
if [[ "${CUOIKY_PANEL:-true}" == true ]]; then
    /usr/bin/python3 scripts/hri_panel.py > log/simulation/panel.log 2>&1 &
    task_panel_pid="$!"
fi
echo 'SẴN SÀNG. Domain mô phỏng riêng: 98.'
if [[ "$task_mode" != --interactive ]]; then
    /usr/bin/python3 tests/gazebo_hri_demo.py 2>&1 | tee log/simulation/demo.log
fi
if [[ "$task_mode" == --test ]]; then exit 0; fi
echo 'Mô phỏng tiếp tục mở. Ctrl+C tại terminal chạy để dừng.'
echo 'Mở terminal khác: source scripts/sim_env.sh; sau đó chạy giọng nói theo README.'
wait "$task_sim_pid"
