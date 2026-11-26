#!/usr/bin/env python3
"""SIMULATION ONLY: semantic ground truth from Gazebo model poses, never real detection."""
import json
import math
import subprocess
import threading
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage


class SimPeople(Node):
    def __init__(self):
        super().__init__('sim_people_ground_truth')
        self.declare_parameter('world','lab_slam')
        self.people={};self.robot=None;self.observed=-1e9
        self.pub=self.create_publisher(String,'/perception/people',10)
        self.create_subscription(TFMessage,'/simulation/model_poses',self.poses,10)
        self.create_timer(.1,self.publish)

    def poses(self,msg):
        people={};robot=None
        for t in msg.transforms:
            name=t.child_frame_id;p=t.transform.translation
            if name.startswith('person_'):people[name]=(p.x,p.y)
            if name in ('turtlebot4','turtlebot4_standard','create3'):robot=(p.x,p.y)
        if robot is not None:
            self.robot=robot;self.people=people;self.observed=time.monotonic()

    def publish(self):
        valid=self.robot is not None and time.monotonic()-self.observed<.75
        people=[]
        if valid:
            for name,(x,y) in self.people.items():
                people.append(dict(id=name,distance=math.hypot(x-self.robot[0],y-self.robot[1])))
        self.pub.publish(String(data=json.dumps(dict(valid=valid,frame_id='base_link',source='gazebo_ground_truth',people=people))))


def main():
    rclpy.init();n=SimPeople()
    try:rclpy.spin(n)
    except KeyboardInterrupt:pass
    finally:n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
