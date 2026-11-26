#!/usr/bin/env python3
"""Drive an odometry route in the known demo room; map comes ONLY from live SLAM."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

from lab_catalog import create_catalog, add_destination
from mapping_geometry import nearest_forward_obstacle


def angle(value):
    return math.atan2(math.sin(value), math.cos(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = Node('lab_slam_scan')
    node.set_parameters([Parameter('use_sim_time', value=True)])
    pub = node.create_publisher(Twist, '/cmd_vel_requested', 1)
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    state = dict(pose=None, odom_at=0, scan=None, scan_at=0, map=None, scans=0, trail=[], diagnostic={})

    def odom(msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        state['pose'] = (p.x, p.y, math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)))
        state['odom_at'] = time.monotonic()
        state['trail'].append((p.x,p.y))

    def scan(msg):
        state.update(scan=msg, scan_at=time.monotonic(), scans=state['scans']+1)

    node.create_subscription(Odometry, '/odom', odom, 10)
    node.create_subscription(LaserScan, '/scan_nav', scan, qos_profile_sensor_data)
    node.create_subscription(OccupancyGrid, '/map', lambda m: state.update(map=m),
        QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))

    def move(v=0.0,w=0.0):
        msg=Twist();msg.linear.x=v;msg.angular.z=w;pub.publish(msg)

    def spin(seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.03)

    def front_clear():
        msg=state['scan']
        if msg is None or time.monotonic()-state['scan_at']>1.0:
            state['diagnostic']={'reason':'stale scan'};return False
        if time.monotonic()-state['odom_at']>1.0:
            state['diagnostic']={'reason':'stale odometry'};return False
        try:
            tr=buffer.lookup_transform('base_link',msg.header.frame_id,Time()).transform
        except Exception as exc:
            state['diagnostic']={'reason':'laser transform unavailable','error':str(exc)};return False
        q=tr.rotation
        yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        nearest=nearest_forward_obstacle(msg.ranges,msg.angle_min,msg.angle_increment,
            msg.range_min,msg.range_max,tr.translation.x,tr.translation.y,yaw)
        state['diagnostic']={'nearest_forward_m':nearest,'sensor_yaw':yaw,'sensor_xy':[tr.translation.x,tr.translation.y],'frame':msg.header.frame_id}
        return nearest is not None and nearest>.5

    started=time.monotonic();waypoints=[]
    try:
        deadline=time.monotonic()+120
        while not (state['pose'] and state['scan'] and state['map']):
            if time.monotonic()>deadline:raise TimeoutError('Chưa nhận odom, scan và map SLAM')
            rclpy.spin_once(node,timeout_sec=.1)
        origin=state['pose']
        print('SLAM ready; initial odometry:',origin,flush=True)
        # Relative to the initial robot heading. Route is scripted for this
        # room; it is not an exploration planner and reads no reference map.
        route=[(2.5,0),(2.5,3.6),(2.5,0),(0,0)]
        for index,(rx,ry) in enumerate(route):
            gx=origin[0]+math.cos(origin[2])*rx-math.sin(origin[2])*ry
            gy=origin[1]+math.sin(origin[2])*rx+math.cos(origin[2])*ry
            print(f'Scanning waypoint {index+1}/{len(route)}: {gx:.2f}, {gy:.2f}',flush=True)
            deadline=time.monotonic()+80
            blocked_at=None
            while True:
                rclpy.spin_once(node,timeout_sec=.04)
                x,y,yaw=state['pose'];distance=math.hypot(gx-x,gy-y)
                if distance<.10:break
                if time.monotonic()>deadline:raise TimeoutError('Waypoint timeout')
                error=angle(math.atan2(gy-y,gx-x)-yaw)
                speed=min(.22,.6*distance) if abs(error)<.3 else 0.0
                if speed and not front_clear():
                    move()
                    blocked_at=blocked_at or time.monotonic()
                    if time.monotonic()-blocked_at>8:
                        raise RuntimeError(f'Obstacle or stale scan blocks route; pose={state["pose"]}; diagnostic={state["diagnostic"]}')
                    continue
                blocked_at=None
                move(speed,max(-.6,min(.6,1.5*error)))
            move();spin(.5)
            waypoints.append(dict(odom=list(state['pose']),index=index))
        move();spin(3)
        msg=state['map']
        free=sum(v==0 for v in msg.data);occupied=sum(v==100 for v in msg.data)
        distance=sum(math.dist(a,b) for a,b in zip(state['trail'],state['trail'][1:]))
        if free*msg.info.resolution**2<25 or state['scans']<100 or distance<10:
            raise RuntimeError('Insufficient map/scan/travel coverage')
        map_prefix=args.output/'map'
        subprocess.run(['ros2','run','nav2_map_server','map_saver_cli','-f',str(map_prefix),
            '--ros-args','-p','use_sim_time:=true','-p','save_map_timeout:=15.0'],check=True)
        spin(1)
        tr=buffer.lookup_transform('map','odom',Time()).transform
        q=tr.rotation;rotation=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))

        def map_pose(pose):
            x,y,yaw=pose
            return dict(x=tr.translation.x+math.cos(rotation)*x-math.sin(rotation)*y,
                        y=tr.translation.y+math.sin(rotation)*x+math.cos(rotation)*y,
                        yaw=angle(yaw+rotation))

        catalog=args.output/'destinations.yaml'
        create_catalog(str(map_prefix)+'.yaml',catalog)
        for number,waypoint_index in enumerate([0,1,3],1):
            add_destination(catalog,f'ban_{number}',f'Bàn số {number}',
                [f'bàn {number}',f'bàn '+{1:'một',2:'hai',3:'ba'}[number]],
                **map_pose(waypoints[waypoint_index]['odom']))
        initial=map_pose(state['pose'])
        (args.output/'initial_pose.json').write_text(json.dumps(initial,indent=2)+'\n')
        report=dict(source='New online SLAM Toolbox map from live Gazebo LiDAR and odometry',
            reference_map_used=False,route='Scripted odometry loop for the known demo room; not autonomous exploration',
            elapsed_sec=round(time.monotonic()-started,2),distance_m=round(distance,3),
            received_scans=state['scans'],free_area_m2=round(free*msg.info.resolution**2,2),
            occupied_cells=occupied,map_cells=[msg.info.width,msg.info.height],
            waypoints=waypoints,localization_initial_pose=initial,passed=True)
        (args.output/'mapping_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        (args.output/'mapping_odom_trail.json').write_text(json.dumps(state['trail'])+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    finally:
        for _ in range(5):move();spin(.05)
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
