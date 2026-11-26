#!/usr/bin/env bash
set -e
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
/usr/bin/python3 "$task_root/scripts/cleanup_sim_processes.py"
rm -f "/tmp/tb4_cuoiky_runtime_${UID}/runner.pid" "/tmp/tb4_cuoiky_runtime_${UID}/current_partition"
echo 'Đã dừng phiên mô phỏng cuối kỳ.'
