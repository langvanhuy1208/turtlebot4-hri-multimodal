#!/usr/bin/env python3
"""Low-speed mapping keyboard control; stop when key repeats cease."""
import argparse
import select
import sys
import termios
import time
import tty

import rclpy
from geometry_msgs.msg import Twist


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--topic', default='/cmd_vel_requested')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error('Mở trong terminal tương tác')
    rclpy.init()
    node = rclpy.create_node('lab_mapping_teleop')
    pub = node.create_publisher(Twist, args.topic, 1)
    settings = termios.tcgetattr(sys.stdin)
    print('Giữ W/S: tiến/lùi 0.12 m/s; A/D: xoay 0.4 rad/s; Space: dừng; Q: thoát.\n'
          'Thả phím: dừng sau tối đa 0.35 giây. Chỉ chạy khi Nav2 đã tắt.', flush=True)
    velocity, turn, last = 0.0, 0.0, 0.0
    try:
        tty.setcbreak(sys.stdin.fileno())
        while rclpy.ok():
            if select.select([sys.stdin], [], [], 0.05)[0]:
                key = sys.stdin.read(1).lower()
                if key in ('q', '\x03'):
                    break
                velocity, turn = {'w': (0.12, 0.0), 's': (-0.12, 0.0),
                                  'a': (0.0, 0.4), 'd': (0.0, -0.4)}.get(key, (0.0, 0.0))
                last = time.monotonic()
            if time.monotonic() - last > 0.35:
                velocity, turn = 0.0, 0.0
            msg = Twist()
            msg.linear.x, msg.angular.z = velocity, turn
            pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        for _ in range(3):
            pub.publish(Twist())
            rclpy.spin_once(node, timeout_sec=0.05)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
