#!/usr/bin/env python3
"""Robot RGB person detector with conservative LiDAR range association.
No identity recognition; only the camera field of view is semantically classified.
"""
import json
import math
import time
from pathlib import Path
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import Image,CameraInfo,LaserScan
from std_msgs.msg import String
from tf2_ros import Buffer,TransformListener
from cv_bridge import CvBridge


def rotate(q,v):
    u=np.array([q.x,q.y,q.z]);return v+2*q.w*np.cross(u,v)+2*np.cross(u,np.cross(u,v))


class People(Node):
    def __init__(self):
        super().__init__('person_perception')
        for k,v in [('model',''),('rgb_topic','oakd/rgb/preview/image_raw'),('info_topic','oakd/rgb/preview/camera_info'),('confidence',.55)]:self.declare_parameter(k,v)
        from ultralytics import YOLO
        import torch
        torch.set_num_threads(1)
        path=Path(self.get_parameter('model').value)
        if not path.is_file():raise ValueError('Local YOLO model required; automatic downloads disabled')
        self.model=YOLO(str(path));self.bridge=CvBridge();self.rgb=self.info=self.scan=None
        self.tf=Buffer();self.listener=TransformListener(self.tf,self)
        self.pub=self.create_publisher(String,'/perception/people',10)
        self.create_subscription(Image,self.get_parameter('rgb_topic').value,lambda m:setattr(self,'rgb',m),qos_profile_sensor_data)
        self.create_subscription(CameraInfo,self.get_parameter('info_topic').value,lambda m:setattr(self,'info',m),qos_profile_sensor_data)
        self.create_subscription(LaserScan,'scan',lambda m:setattr(self,'scan',m),qos_profile_sensor_data)
        self.create_timer(.2,self.tick)

    def tick(self):
        out=dict(valid=False,frame_id='base_link',source='rgb_yolo_lidar',people=[])
        try:
            if any(m is None for m in (self.rgb,self.info,self.scan)):raise ValueError('Waiting for RGB, camera calibration and scan')
            now=self.get_clock().now()
            if any(not 0<=(now-Time.from_msg(m.header.stamp)).nanoseconds/1e9<.8 for m in (self.rgb,self.scan)):raise ValueError('Sensor stale')
            if abs((Time.from_msg(self.rgb.header.stamp)-Time.from_msg(self.scan.header.stamp)).nanoseconds/1e9)>.4:raise ValueError('RGB and LiDAR out of sync')
            if self.rgb.width!=self.info.width or self.rgb.height!=self.info.height:raise ValueError('CameraInfo size does not match RGB')
            camera=self.tf.lookup_transform('base_link',self.rgb.header.frame_id,Time.from_msg(self.rgb.header.stamp)).transform
            laser=self.tf.lookup_transform('base_link',self.scan.header.frame_id,Time.from_msg(self.scan.header.stamp)).transform
            scan=self.scan;r=np.array(scan.ranges);a=scan.angle_min+np.arange(len(r))*scan.angle_increment
            good=np.isfinite(r)&(r>=scan.range_min)&(r<=scan.range_max)
            points=np.array([rotate(laser.rotation,np.array([d*math.cos(t),d*math.sin(t),0]))+np.array([laser.translation.x,laser.translation.y,laser.translation.z]) for d,t in zip(r[good],a[good])])
            result=self.model.predict(self.bridge.imgmsg_to_cv2(self.rgb,'bgr8'),classes=[0],conf=self.get_parameter('confidence').value,imgsz=320,device='cpu',verbose=False)[0]
            for box in result.boxes:
                x1,y1,x2,y2=box.xyxy[0].tolist();fx=self.info.k[0];cx=self.info.k[2]
                if fx<=0:raise ValueError('Invalid focal length')
                direction=rotate(camera.rotation,np.array([((x1+x2)/2-cx)/fx,0,1]))
                bearing=math.atan2(direction[1],direction[0]);half=max(.08,math.atan((x2-x1)/2/fx))
                if len(points):
                    delta=np.arctan2(np.sin(np.arctan2(points[:,1],points[:,0])-bearing),np.cos(np.arctan2(points[:,1],points[:,0])-bearing))
                    matches=points[np.abs(delta)<half]
                else:matches=[]
                if not len(matches):raise ValueError('Person detected but range unavailable; fail closed')
                out['people'].append(dict(distance=float(np.min(np.linalg.norm(matches[:,:2],axis=1))),confidence=float(box.conf[0]),bearing=bearing))
            out['valid']=True
        except Exception as e:out['reason']=str(e)
        self.pub.publish(String(data=json.dumps(out)))


def main():
    rclpy.init();n=People()
    try:rclpy.spin(n)
    except KeyboardInterrupt:pass
    finally:n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
