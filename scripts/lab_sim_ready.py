#!/usr/bin/env python3
"""Initialize localization in the map frame measured at the end of SLAM."""
import argparse
import json
import math
from pathlib import Path
import time

import numpy as np
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer,TransformListener
from lab_catalog import LabCatalog


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True)
    args=parser.parse_args()
    catalog=LabCatalog(args.folder/'destinations.yaml')
    pose=json.loads((args.folder/'initial_pose.json').read_text())
    rclpy.init();node=Node('lab_slam_localization_ready')
    node.set_parameters([Parameter('use_sim_time',value=True)])
    received={'map':None}
    node.create_subscription(OccupancyGrid,'/map',lambda m:received.update(map=m),
        QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    pub=node.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
    lifecycle=node.create_client(GetState,'/bt_navigator/get_state')
    buffer=Buffer();listener=TransformListener(buffer,node)
    active=False;future=None;last_initial=0;checked=False
    try:
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.1)
            grid=received['map']
            if grid is not None and not checked:
                m=catalog.map
                if (grid.info.width,grid.info.height)!=(m.width,m.height):raise RuntimeError('Wrong loaded map dimensions')
                if abs(grid.info.resolution-m.resolution)>1e-6:raise RuntimeError('Wrong map resolution')
                if abs(grid.info.origin.position.x-m.origin[0])>1e-6 or abs(grid.info.origin.position.y-m.origin[1])>1e-6:raise RuntimeError('Wrong map origin')
                actual=np.asarray(grid.data).reshape(m.height,m.width)[::-1]
                occupancy=m.image.astype(float)/255
                if not m.meta.get('negate',0):occupancy=1-occupancy
                expected=np.full(m.image.shape,-1,dtype=np.int16)
                expected[occupancy<float(m.meta['free_thresh'])]=0
                expected[occupancy>float(m.meta['occupied_thresh'])]=100
                if not np.array_equal(actual,expected):raise RuntimeError('Loaded /map differs from the newly saved SLAM map')
                checked=True
            if grid is not None and buffer.can_transform('odom','base_link',Time()) and not buffer.can_transform('map','base_link',Time()) and time.monotonic()-last_initial>1:
                msg=PoseWithCovarianceStamped();msg.header.frame_id='map';msg.header.stamp=node.get_clock().now().to_msg()
                msg.pose.pose.position.x=pose['x'];msg.pose.pose.position.y=pose['y']
                msg.pose.pose.orientation.z=math.sin(pose['yaw']/2);msg.pose.pose.orientation.w=math.cos(pose['yaw']/2)
                msg.pose.covariance[0]=msg.pose.covariance[7]=msg.pose.covariance[35]=.05
                pub.publish(msg);last_initial=time.monotonic()
            if future is not None and future.done():active=future.result().current_state.id==3;future=None
            if not active and future is None and lifecycle.service_is_ready():future=lifecycle.call_async(GetState.Request())
            if checked and active and buffer.can_transform('map','base_link',Time()):
                print('READY: loaded map equals new SLAM map, AMCL/TF/Nav2 active',flush=True);return
        raise TimeoutError('Localization/Nav2 not ready')
    finally:node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
