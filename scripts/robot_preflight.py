#!/usr/bin/env python3
"""Read-only deployment checks; never publishes velocity or navigation goals."""
import argparse
import json
from pathlib import Path
import time
import yaml
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan,Image,CameraInfo
from nav_msgs.msg import Odometry
from tf2_ros import Buffer,TransformListener
from lab_catalog import LabCatalog


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--seconds',type=float,default=10);a=p.parse_args()
    cfg=yaml.safe_load(a.profile.read_text());catalog=LabCatalog(a.catalog)
    ns=cfg.get('namespace','').strip('/');prefix='/'+ns if ns else ''
    rclpy.init();n=rclpy.create_node('tb4_deployment_check',namespace=prefix,cli_args=['--ros-args','-r','/tf:='+prefix+'/tf','-r','/tf_static:='+prefix+'/tf_static'])
    b=Buffer();l=TransformListener(b,n);counts={};last={}
    def got(key,m):counts[key]=counts.get(key,0)+1;last[key]=m
    for key,typ,topic in [('scan',LaserScan,'scan'),('odom',Odometry,'odom'),('rgb',Image,cfg.get('rgb_topic','oakd/rgb/preview/image_raw')),('camera_info',CameraInfo,cfg.get('info_topic','oakd/rgb/preview/camera_info'))]:
        n.create_subscription(typ,topic,lambda m,k=key:got(k,m),qos_profile_sensor_data)
    end=time.monotonic()+a.seconds
    while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
    checks={k:counts.get(k,0)>0 for k in ['scan','odom','rgb','camera_info']}
    checks['tf_laser']=bool(last.get('scan') and b.can_transform('base_link',last['scan'].header.frame_id,rclpy.time.Time()))
    checks['tf_camera']=bool(last.get('rgb') and b.can_transform('base_link',last['rgb'].header.frame_id,rclpy.time.Time()))
    checks['localized']=b.can_transform('map','base_link',rclpy.time.Time())
    publishers=n.get_publishers_info_by_topic(prefix+'/cmd_vel')
    checks['velocity_publisher_exclusive']=len(publishers)==1 and publishers[0].node_name=='social_safety'
    print(json.dumps(dict(passed=all(checks.values()),counts=counts,checks=checks,catalog=str(catalog.path),namespace=ns,note='Read-only checks; sensor accuracy and low-speed physical trials still required.'),ensure_ascii=False,indent=2))
    n.destroy_node();rclpy.shutdown()
    if not all(checks.values()):raise SystemExit(2)
if __name__=='__main__':main()
