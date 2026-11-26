#!/usr/bin/env bash
# Source in a fresh terminal to connect to a physical TurtleBot 4. Does not move it.
# Network settings are deliberately kept in an untracked local file.
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/humble/setup.bash
unset CYCLONEDDS_URI FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE ROS_DISCOVERY_SERVER ROBOT_NAMESPACE
connection_file="${TB4_CONNECTION_FILE:-$task_root/config/robot_connection.env}"
if [[ ! -r "$connection_file" ]]; then
  echo "Thiếu cấu hình cục bộ: $connection_file" >&2
  echo "Tạo bằng: cp config/robot_connection.env.example config/robot_connection.env" >&2
  return 2 2>/dev/null || exit 2
fi
source "$connection_file"
: "${ROS_DOMAIN_ID:?ROS_DOMAIN_ID phải được đặt trong cấu hình robot}"
: "${RMW_IMPLEMENTATION:?RMW_IMPLEMENTATION phải được đặt trong cấu hình robot}"
export ROS_LOCALHOST_ONLY=0
