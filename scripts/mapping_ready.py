#!/usr/bin/env python3
import argparse
from pathlib import Path
import subprocess
import time
import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSProfile,DurabilityPolicy
from lab_catalog import create_catalog


def main():
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
    a.folder.mkdir(parents=True,exist_ok=True);rclpy.init();n=rclpy.create_node('mapping_bootstrap')
    seen=[];n.create_subscription(OccupancyGrid,'map',lambda m:seen.append(m.info.width*m.info.height),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    end=time.monotonic()+100
    while not seen:
        rclpy.spin_once(n,timeout_sec=.2)
        if time.monotonic()>end:raise TimeoutError('SLAM map unavailable')
    subprocess.run(['ros2','run','nav2_map_server','map_saver_cli','-f',str(a.folder/'bootstrap'),'--ros-args','-p','use_sim_time:=true'],check=True,timeout=25)
    catalog=a.folder/'destinations.yaml'
    if catalog.exists():catalog.unlink()
    create_catalog(a.folder/'bootstrap.yaml',catalog)
    n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
