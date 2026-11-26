#!/usr/bin/env python3
import json
import math
from pathlib import Path
import time
import rclpy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_msgs.msg import String


def main():
    rclpy.init();n=rclpy.create_node('manual_mapping_probe');s={'mode':None,'pose':None,'v':0}
    c=n.create_publisher(String,'/mapping/control',10)
    manual=n.create_publisher(Twist,'/cmd_vel_manual',10);nav=n.create_publisher(Twist,'/cmd_vel_requested',10)
    n.create_subscription(String,'/mapping/mode',lambda m:s.update(mode=m.data),10)
    n.create_subscription(Odometry,'odom',lambda m:s.update(pose=(m.pose.pose.position.x,m.pose.pose.position.y)),10)
    n.create_subscription(Twist,'cmd_vel',lambda m:s.update(v=m.linear.x),10)
    def spin(t):
        end=time.monotonic()+t
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.03)
    def wait(p):
        end=time.monotonic()+15
        while not p():
            spin(.05)
            if time.monotonic()>end:raise TimeoutError(str(s))
    error=None;report={}
    try:
        wait(lambda:c.get_subscription_count()>0 and s['pose'] is not None)
        c.publish(String(data='manual'));wait(lambda:s['mode']=='manual');spin(1)
        m=Twist();m.linear.x=.2
        for _ in range(15):nav.publish(m);spin(.05)
        assert abs(s['v'])<1e-6,s
        report['nav_input_ignored_in_manual']=True
        start=s['pose'];m.linear.x=.07
        for _ in range(35):manual.publish(m);spin(.05)
        manual.publish(Twist());spin(.5)
        report['travel_m']=math.dist(start,s['pose']);assert report['travel_m']>.03,report
        c.publish(String(data='stop'));wait(lambda:s['mode']=='stop');spin(.2)
        manual.publish(m);nav.publish(m);spin(.3);assert abs(s['v'])<1e-6,s
        report['all_input_ignored_in_stop']=True
    except Exception as e:error=str(e);raise
    finally:
        c.publish(String(data='stop'));manual.publish(Twist());nav.publish(Twist());spin(.1)
        out=Path(__file__).resolve().parents[1]/'results/manual_mapping_results.json'
        out.write_text(json.dumps(dict(passed=error is None,error=error,results=report),indent=2)+'\n')
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
