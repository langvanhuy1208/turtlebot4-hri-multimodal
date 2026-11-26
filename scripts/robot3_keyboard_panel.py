#!/usr/bin/env python3
"""Physical robot3 keyboard teleop; motion only while an operator holds a key."""
import os
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk

import rclpy
from geometry_msgs.msg import Twist
from irobot_create_msgs.action import Undock
from irobot_create_msgs.msg import DockStatus
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState
from keyboard_control import keyboard_velocity


class KeyboardRobot(Node):
    def __init__(self):
        super().__init__('robot3_keyboard_teleop')
        self.pub=self.create_publisher(Twist,'/robot3/cmd_vel',1)
        self.undock=ActionClient(self,Undock,'/robot3/undock')
        self.odom_at=0;self.docked=None;self.battery=None;self.speed=(0.0,0.0)
        self.undocking=False;self.undock_handle=None;self.cancel_requested=False;self.cancel_sent=False
        self.message='Đang chờ kết nối cảm biến…'
        self.create_subscription(Odometry,'/robot3/odom',self.on_odom,qos_profile_sensor_data)
        self.create_subscription(DockStatus,'/robot3/dock_status',lambda m:setattr(self,'docked',m.is_docked),qos_profile_sensor_data)
        self.create_subscription(BatteryState,'/robot3/battery_state',lambda m:setattr(self,'battery',m.percentage*100),qos_profile_sensor_data)

    def on_odom(self,msg):
        self.odom_at=time.monotonic()
        self.speed=(msg.twist.twist.linear.x,msg.twist.twist.angular.z)

    def connected(self):
        return time.monotonic()-self.odom_at<=1.0 and self.pub.get_subscription_count()>0

    def drive(self,v=0.0,w=0.0):
        if not rclpy.ok():return
        msg=Twist();msg.linear.x=float(v);msg.angular.z=float(w);self.pub.publish(msg)

    def stop(self):
        self.drive()
        if self.undocking:
            self.cancel_requested=True;self.cancel_undock()

    def cancel_undock(self):
        if self.undock_handle and not self.cancel_sent:
            self.cancel_sent=True;self.undock_handle.cancel_goal_async()

    def leave_dock(self):
        if not self.connected() or self.docked is not True or self.undocking:return
        if not self.undock.server_is_ready():
            self.message='Chưa kết nối được chức năng rời dock';return
        self.drive();self.undocking=True;self.cancel_requested=False;self.cancel_sent=False
        self.message='Đang rời dock — Space để hủy'
        self.undock.send_goal_async(Undock.Goal()).add_done_callback(self.on_undock_goal)

    def on_undock_goal(self,future):
        try:
            self.undock_handle=future.result()
            if not self.undock_handle.accepted:raise RuntimeError('Robot từ chối rời dock')
            self.undock_handle.get_result_async().add_done_callback(self.on_undock_result)
            if self.cancel_requested:self.cancel_undock()
        except Exception as exc:
            self.undocking=False;self.message=str(exc);self.undock_handle=None

    def on_undock_result(self,future):
        try:
            result=future.result()
            self.message=('Đã hủy rời dock' if self.cancel_requested else
                          'Đã rời dock, có thể điều khiển' if result.status==4 and not result.result.is_docked else 'Chưa rời được dock')
        except Exception as exc:self.message=str(exc)
        self.undocking=False;self.undock_handle=None;self.drive()


def main():
    pidfile=Path('/tmp/tb4_robot3_keyboard.pid')
    if pidfile.exists():
        try:
            old=int(pidfile.read_text());args=(Path('/proc')/str(old)/'cmdline').read_bytes()
            if b'robot3_keyboard_panel.py' in args:
                print('Robot3 keyboard panel is already running');return
        except (ValueError,OSError):pass
    rclpy.init();node=KeyboardRobot();root=tk.Tk()
    root.title('TurtleBot 4 robot3 — Điều khiển bàn phím');root.geometry('740x590')
    pidfile.write_text(str(os.getpid()))
    keys=set();pending={};closed=False;sent=(0.0,0.0)
    status=tk.StringVar(value='Đang kết nối robot3…')
    telemetry=tk.StringVar(value='Robot thật · kiểm tra DDS/namespace trước khi chạy')
    ttk.Label(root,text='TurtleBot 4 · Bàn phím laptop',font=('',20)).pack(pady=18)
    ttk.Label(root,text='Giữ W/A/S/D hoặc phím mũi tên · Thả phím để dừng',font=('',12)).pack(pady=6)
    ttk.Label(root,textvariable=status,wraplength=690,font=('',13)).pack(pady=10)
    ttk.Label(root,textvariable=telemetry,wraplength=690).pack(pady=6)
    board=ttk.Frame(root);board.pack(pady=14)

    def stop():
        keys.clear()
        for timer in pending.values():root.after_cancel(timer)
        pending.clear();node.stop()

    def press(key):
        if key in pending:root.after_cancel(pending.pop(key))
        if key in ('space','escape'):stop();return
        if key=='q':close();return
        if key in ('w','a','s','d','up','left','down','right'):keys.add(key)

    def release(key):
        if key in pending:root.after_cancel(pending.pop(key))
        def finish():pending.pop(key,None);keys.discard(key)
        pending[key]=root.after(25,finish)

    for key,text,row,col in [('w','W / ↑\nTIẾN',0,1),('a','A / ←\nTRÁI',1,0),('s','S / ↓\nLÙI',1,1),('d','D / →\nPHẢI',1,2)]:
        button=tk.Button(board,text=text,width=15,height=3,font=('',12))
        button.grid(row=row,column=col,padx=5,pady=5)
        button.bind('<ButtonPress-1>',lambda e,k=key:press(k))
        button.bind('<ButtonRelease-1>',lambda e,k=key:release(k))
        button.bind('<Leave>',lambda e,k=key:keys.discard(k))
    tk.Button(root,text='SPACE — DỪNG',font=('',16,'bold'),bg='#b52222',fg='white',command=stop).pack(pady=10,ipadx=70,ipady=8)
    undock=ttk.Button(root,text='RỜI DOCK',command=node.leave_dock,state='disabled');undock.pack(pady=8)
    ttk.Label(root,text='Tốc độ: 0,10 m/s · Xoay: 0,35 rad/s · Q để đóng').pack(pady=6)
    root.bind('<KeyPress>',lambda e:press(e.keysym.lower()))
    root.bind('<KeyRelease>',lambda e:release(e.keysym.lower()))
    def lost_focus(_):
        def check():
            if not closed and root.focus_displayof() is None:stop()
        root.after_idle(check)
    root.bind('<FocusOut>',lost_focus)

    def tick():
        nonlocal sent
        if closed:return
        if not rclpy.ok():close();return
        for _ in range(8):rclpy.spin_once(node,timeout_sec=0)
        connected=node.connected()
        enabled=connected and node.docked is False and not node.undocking
        if not connected:
            stop();status.set('Chưa có dữ liệu robot mới — xe không nhận lệnh phím')
        elif node.undocking:status.set(node.message)
        elif node.docked is True:
            keys.clear();status.set('Robot đang trên dock. Bấm RỜI DOCK để bắt đầu.')
        elif node.docked is None:
            keys.clear();status.set('Đang chờ trạng thái dock…')
        else:status.set('SẴN SÀNG — giữ phím để chạy; Space để dừng')
        undock.config(state='normal' if connected and node.docked is True and not node.undocking and node.undock.server_is_ready() else 'disabled')
        velocity=keyboard_velocity(keys,enabled)
        # Do not stream cmd_vel while the robot's own undock action runs.
        if not node.undocking:node.drive(*velocity)
        if velocity!=sent:
            node.get_logger().info(f'Keyboard command: v={velocity[0]:.2f}, w={velocity[1]:.2f}')
            sent=velocity
        pin='—' if node.battery is None else f'{node.battery:.0f}%'
        telemetry.set(f'Pin {pin} · Đo được {node.speed[0]:.2f} m/s, {node.speed[1]:.2f} rad/s')
        root.after(50,tick)

    def close():
        nonlocal closed
        if closed:return
        stop()
        if rclpy.ok():
            until=time.monotonic()+.35
            while time.monotonic()<until:
                rclpy.spin_once(node,timeout_sec=.03);node.drive()
        closed=True;root.destroy()

    root.protocol('WM_DELETE_WINDOW',close);root.after(100,tick);root.focus_force()
    try:root.mainloop()
    finally:
        if rclpy.ok():node.stop()
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
        if pidfile.exists() and pidfile.read_text().strip()==str(os.getpid()):pidfile.unlink()


if __name__=='__main__':main()
