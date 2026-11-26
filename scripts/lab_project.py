#!/usr/bin/env python3
"""Lab workflow CLI: doctor, save-map, init, mark, list. No implicit motion."""
import argparse
import json
import math
import subprocess
import time
from pathlib import Path

from lab_catalog import LabCatalog, add_destination, create_catalog


def current_pose(base_frame, sim_time, timeout):
    import rclpy
    from rclpy.time import Time
    from tf2_ros import Buffer, TransformListener, TransformException
    rclpy.init()
    node = rclpy.create_node('lab_mark_pose')
    node.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=sim_time)])
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            try:
                transform = buffer.lookup_transform('map', base_frame, Time())
                age = (node.get_clock().now() - Time.from_msg(transform.header.stamp)).nanoseconds / 1e9
                if not -0.5 <= age <= 1.5:
                    continue
                t, q = transform.transform.translation, transform.transform.rotation
                yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
                return t.x, t.y, yaw
            except TransformException:
                pass
        raise RuntimeError(f'Không có TF map -> {base_frame} mới; kiểm tra định vị/SLAM và clock')
    finally:
        del listener
        node.destroy_node()
        rclpy.shutdown()


def doctor(seconds, scan_topic, odom_topic):
    import os
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan
    from nav_msgs.msg import Odometry
    rclpy.init()
    node = rclpy.create_node('lab_connection_check')
    counts = dict(scan=0, odom=0)
    def receive(key):
        def callback(_):
            counts[key] += 1
        return callback
    node.create_subscription(LaserScan, scan_topic, receive('scan'), qos_profile_sensor_data)
    node.create_subscription(Odometry, odom_topic, receive('odom'), qos_profile_sensor_data)
    try:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
        report = dict(ROS_DOMAIN_ID=os.environ.get('ROS_DOMAIN_ID', '0'),
                      RMW_IMPLEMENTATION=os.environ.get('RMW_IMPLEMENTATION', 'default'),
                      ROS_LOCALHOST_ONLY=os.environ.get('ROS_LOCALHOST_ONLY', '0'),
                      received=counts, nodes=node.get_node_names(),
                      topics=dict(node.get_topic_names_and_types()))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not all(counts.values()):
            raise RuntimeError('Chưa nhận đủ scan/odom. Kiểm tra nguồn robot, Wi-Fi, domain, DDS và tên topic')
        print('Đã nhận scan và odom. Kiểm tra nguồn topic là robot thật trước khi điều khiển.')
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    check = sub.add_parser('doctor', help='Check live DDS sensor reception; never moves robot')
    check.add_argument('--seconds', type=float, default=8)
    check.add_argument('--scan-topic', default='/scan')
    check.add_argument('--odom-topic', default='/odom')
    save = sub.add_parser('save-map')
    save.add_argument('--output', type=Path, required=True, help='Prefix, e.g. maps/lab/map')
    save.add_argument('--sim-time', action='store_true')
    init = sub.add_parser('init')
    init.add_argument('--map', type=Path, required=True)
    init.add_argument('--catalog', type=Path, required=True)
    init.add_argument('--clearance', type=float, default=0.35)
    mark = sub.add_parser('mark')
    mark.add_argument('--catalog', type=Path, required=True)
    mark.add_argument('--id', required=True)
    mark.add_argument('--name', required=True)
    mark.add_argument('--alias', action='append', default=[])
    mark.add_argument('--pose', nargs=3, type=float, metavar=('X', 'Y', 'YAW'),
                      help='Explicit map coordinates; omit to capture live TF')
    mark.add_argument('--base-frame', default='base_link')
    mark.add_argument('--sim-time', action='store_true')
    mark.add_argument('--timeout', type=float, default=10)
    listing = sub.add_parser('list')
    listing.add_argument('--catalog', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == 'doctor':
            if not math.isfinite(args.seconds) or args.seconds <= 0:
                raise ValueError('--seconds phải > 0')
            doctor(args.seconds, args.scan_topic, args.odom_topic)
        elif args.action == 'save-map':
            output = args.output.expanduser().resolve()
            if any(Path(str(output) + suffix).exists() for suffix in ('.yaml', '.pgm', '.png')):
                raise ValueError('Bản đồ đã tồn tại; chọn tên mới để giữ bản đồ và catalog cũ')
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['ros2', 'run', 'nav2_map_server', 'map_saver_cli', '-f', str(output),
                            '--ros-args', '-p', 'save_map_timeout:=10.0',
                            '-p', 'use_sim_time:=' + str(args.sim_time).lower()], check=True)
            from semantic_map import OccupancyMap
            OccupancyMap(str(output) + '.yaml')
            print('Đã lưu bản đồ:', str(output) + '.yaml')
        elif args.action == 'init':
            create_catalog(args.map, args.catalog, args.clearance)
            print('Đã tạo catalog trống:', args.catalog)
        elif args.action == 'mark':
            if not math.isfinite(args.timeout) or args.timeout <= 0:
                raise ValueError('--timeout phải > 0')
            pose = args.pose or current_pose(args.base_frame, args.sim_time, args.timeout)
            add_destination(args.catalog, args.id, args.name, args.alias, *pose)
            print(json.dumps(dict(id=args.id, name=args.name, pose=pose), ensure_ascii=False))
        elif args.action == 'list':
            catalog = LabCatalog(args.catalog)
            print(yaml_dump(catalog.data['regions']))
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Lỗi: {exc}\n')


def yaml_dump(data):
    import yaml
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


if __name__ == '__main__':
    main()
