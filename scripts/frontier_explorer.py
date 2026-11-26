#!/usr/bin/env python3
"""Live SLAM frontier exploration; no predefined route or reference map."""
import json
import math
import time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid,Odometry
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import String
from tf2_ros import Buffer,TransformListener
from frontier_core import frontiers


class Explorer(Node):
    def __init__(self):
        super().__init__('frontier_explorer')
        self.map=None;self.map_at=-1e9;self.mode='manual';self.goal=None;self.pending=False
        self.failed=[];self.current=None;self.attempted=0;self.succeeded=0
        self.travel=0.;self.last_odom=None
        self.create_subscription(Odometry,'odom',self.odometry,10)
        self.last_change=time.monotonic();self.started=None;self.goal_at=None
        self.tf=Buffer();self.listener=TransformListener(self.tf,self)
        self.client=ActionClient(self,NavigateToPose,'navigate_to_pose')
        self.pub=self.create_publisher(String,'/mapping/status',10)
        self.mode_pub=self.create_publisher(String,'/mapping/mode',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(OccupancyGrid,'map',self.on_map,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(String,'/mapping/control',self.control,10)
        self.create_timer(1.,self.tick);self.publish('manual')

    def publish(self,state,**fields):
        self.pub.publish(String(data=json.dumps(dict(state=state,attempted=self.attempted,succeeded=self.succeeded,travelled_m=self.travel,**fields))))
        # Manual control is enabled only after pending/active Nav2 action is terminal.
        effective='auto' if self.goal or self.pending else self.mode
        self.mode_pub.publish(String(data=effective))

    def odometry(self,msg):
        p=msg.pose.pose.position
        if self.last_odom:self.travel+=math.hypot(p.x-self.last_odom[0],p.y-self.last_odom[1])
        self.last_odom=(p.x,p.y)

    def on_map(self,m):self.map=m;self.map_at=time.monotonic()

    def control(self,m):
        if m.data not in ('auto','manual','stop'):return
        self.mode=m.data
        if self.mode=='auto':
            self.started=time.monotonic();self.failed=[]
        elif self.goal:self.goal.cancel_goal_async()
        self.publish(self.mode)

    def response(self,f):
        try:
            self.goal=f.result();self.pending=False
            if not self.goal.accepted:self.goal=None;self.failed.append(self.current);return
            self.goal.get_result_async().add_done_callback(self.result)
            if self.mode!='auto':self.goal.cancel_goal_async()
        except Exception as e:
            self.pending=False;self.goal=None;self.publish('error',reason=str(e))

    def result(self,f):
        try:
            if f.result().status==4:
                self.succeeded+=1
                self.failed.append(self.current)
            else:self.failed.append(self.current)
        except Exception:self.failed.append(self.current)
        self.goal=None;self.pending=False;self.publish(self.mode)

    def tick(self):
        self.publish(self.mode)
        if self.mode!='auto':return
        if self.started and time.monotonic()-self.started>600:
            self.mode='stop'
            if self.goal:self.goal.cancel_goal_async()
            self.publish('limit_reached');return
        if self.goal or self.pending:
            if self.goal and time.monotonic()-self.goal_at>60:
                self.goal.cancel_goal_async()
            return
        if not self.map or time.monotonic()-self.map_at>3 or not self.client.server_is_ready():return
        try:
            t=self.tf.lookup_transform(self.map.header.frame_id,'base_link',rclpy.time.Time())
            m=self.map;res=m.info.resolution;o=m.info.origin.position
            # slam_toolbox occupancy grids have zero origin yaw; refuse rotated grids.
            if abs(m.info.origin.orientation.z)>1e-6:raise ValueError('Rotated occupancy grid unsupported')
            x=int((t.transform.translation.x-o.x)/res);y=int((t.transform.translation.y-o.y)/res)
            grid=np.array(m.data).reshape(m.info.height,m.info.width)
            candidates=frontiers(grid,res,(x,y))
            targets=[]
            for c in candidates:
                wx=o.x+(c['x']+.5)*res;wy=o.y+(c['y']+.5)*res
                if all(math.hypot(wx-a,wy-b)>.7 for a,b in self.failed):targets.append((wx,wy))
            if not targets:
                self.mode='stop';self.publish('exploration_finished',reason='No reachable untried frontier',free_area_m2=float(np.sum((grid>=0)&(grid<25))*res*res));return
            wx,wy=targets[0];self.current=(wx,wy);g=NavigateToPose.Goal()
            g.pose.header=m.header;g.pose.header.stamp=self.get_clock().now().to_msg()
            g.pose.pose.position.x=wx;g.pose.pose.position.y=wy;g.pose.pose.orientation.w=1.
            self.pending=True;self.goal_at=time.monotonic();self.attempted+=1
            self.client.send_goal_async(g).add_done_callback(self.response)
            self.publish('exploring',target=[wx,wy])
        except Exception as e:self.publish('waiting',reason=str(e))


def main():
    rclpy.init();n=Explorer()
    try:rclpy.spin(n)
    except KeyboardInterrupt:pass
    finally:
        if n.goal:n.goal.cancel_goal_async()
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
