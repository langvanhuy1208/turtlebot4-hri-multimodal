#!/usr/bin/env python3
"""Single final cmd_vel publisher; all upstream sources must use cmd_vel_requested."""
import json
import math
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from social_safety import Safety


class Guard(Node):
    def __init__(self):
        super().__init__('social_safety')
        for k,v in [('warning_distance',1.5),('stop_distance',.8),('clear_hold',1.),('sensor_timeout',1.)]:self.declare_parameter(k,v)
        self.guard=Safety(*[self.get_parameter(k).value for k in ['warning_distance','stop_distance','clear_hold','sensor_timeout']])
        self.command=Twist();self.command_at=self.scan_at=self.people_at=-1e9
        self.mode='navigation'
        self.nearest_obstacle=self.nearest_person=float('inf');self.last_state=None
        self.output=self.create_publisher(Twist,'cmd_vel',10)
        self.status=self.create_publisher(String,'/hri/safety',10)
        self.create_subscription(Twist,'cmd_vel_requested',lambda m:self.velocity(m,'nav'),10)
        self.create_subscription(Twist,'cmd_vel_manual',lambda m:self.velocity(m,'manual'),10)
        self.create_subscription(String,'/mapping/mode',self.mapping_mode,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(LaserScan,'scan',self.scan,qos_profile_sensor_data)
        self.create_subscription(String,'/perception/people',self.people,10)
        self.create_timer(.05,self.tick)

    def mapping_mode(self,m):
        if m.data!=self.mode:
            self.command=Twist();self.command_at=-1e9
        self.mode=m.data

    def velocity(self,m,source):
        if self.mode=='manual' and source!='manual':return
        if self.mode in ('auto','navigation') and source!='nav':return
        if self.mode=='stop':return
        if all(math.isfinite(x) for x in (m.linear.x,m.linear.y,m.angular.z)):
            self.command=m;self.command_at=time.monotonic()

    def scan(self,m):
        age=(self.get_clock().now()-rclpy.time.Time.from_msg(m.header.stamp)).nanoseconds/1e9
        if not 0<=age<=self.guard.timeout:return
        # Conservative all-round footprint protection works for forward/backward/rotation.
        ranges=[r for r in m.ranges if math.isfinite(r) and m.range_min<=r<=m.range_max]
        if ranges:
            self.nearest_obstacle=min(ranges);self.scan_at=time.monotonic()

    def people(self,m):
        try:
            data=json.loads(m.data)
            # Publisher heartbeat represents a completed observation, not absence of messages.
            if not data.get('valid') or data.get('frame_id')!='base_link':return
            people=data['people'];distances=[float(p['distance']) for p in people]
            if any(not math.isfinite(d) or d<0 for d in distances):return
            self.nearest_person=min(distances,default=float('inf'));self.people_at=time.monotonic()
        except (ValueError,KeyError,TypeError):pass

    def tick(self):
        now=time.monotonic()
        scale,state=self.guard.evaluate(now,now-self.scan_at,now-self.people_at,self.nearest_person,self.nearest_obstacle,now-self.command_at)
        m=Twist();m.linear.x=max(-.26,min(.26,self.command.linear.x))*scale
        m.angular.z=max(-1.,min(1.,self.command.angular.z))*scale
        self.output.publish(m)
        if state!=self.last_state:
            self.status.publish(String(data=json.dumps(dict(state=state,scale=scale,nearest_person_m=self.nearest_person if math.isfinite(self.nearest_person) else None))))
            self.last_state=state


def main():
    rclpy.init();n=Guard()
    try:rclpy.spin(n)
    except KeyboardInterrupt:pass
    finally:n.output.publish(Twist());n.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
