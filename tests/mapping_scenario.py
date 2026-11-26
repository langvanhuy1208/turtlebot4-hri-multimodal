#!/usr/bin/env python3
"""Observe frontier SLAM, stop, then save the live map through HRI confirmation."""
import json
import math
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy
from nav_msgs.msg import OccupancyGrid,Odometry
from std_msgs.msg import String


def main():
    root=Path(__file__).resolve().parents[1];rclpy.init();n=Node('mapping_scenario')
    state={'mapping':None,'mode':None,'map':None,'hri':None};trail=[];events=[]
    v=n.create_publisher(String,'/hri/voice',10);control=n.create_publisher(String,'/mapping/control',10)
    gesture=n.create_publisher(String,'/detected_gesture',10)
    def status(m):state['mapping']=json.loads(m.data);events.append(state['mapping'])
    n.create_subscription(String,'/mapping/status',status,20)
    n.create_subscription(String,'/mapping/mode',lambda m:state.update(mode=m.data),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    n.create_subscription(String,'/hri/status',lambda m:state.update(hri=json.loads(m.data)),20)
    n.create_subscription(OccupancyGrid,'map',lambda m:state.update(map=m),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    n.create_subscription(Odometry,'odom',lambda m:trail.append((m.pose.pose.position.x,m.pose.pose.position.y)),10)
    def wait(p,timeout=30):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(n,timeout_sec=.05)
            if p():return
        raise TimeoutError(str(state.get('mapping'))+' '+str(state.get('hri')))
    def spin(t):
        end=time.monotonic()+t
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.05)
    error=None;report={};name='kiem thu '+time.strftime('%Y%m%d %H%M%S')
    try:
        wait(lambda:state['map'] is not None and state['mapping'] is not None and v.get_subscription_count())
        initial=sum(0<=x<25 for x in state['map'].data)*state['map'].info.resolution**2
        # Observe a finite exploration run. Inability to find a frontier is reported, never hidden as success.
        wait(lambda:any(e['state'] in ('exploration_finished','limit_reached') for e in events) or state['mapping'].get('succeeded',0)>=3 or (state['mode']=='stop' and state['mapping'].get('attempted',0)>0),300)
        report['explorer']=state['mapping'];control.publish(String(data='stop'))
        wait(lambda:state['mode']=='stop',20);spin(2)
        final=sum(0<=x<25 for x in state['map'].data)*state['map'].info.resolution**2
        report.update(initial_observed_area_m2=initial,final_area_m2=final,observed_travel_m=sum(math.dist(a,b) for a,b in zip(trail,trail[1:])))
        assert max(e.get('succeeded',0) for e in events)>=1,events[-5:]
        assert max(e.get('travelled_m',0) for e in events)>.2,events[-5:]
        v.publish(String(data='Lưu bản đồ '+name));wait(lambda:state['hri'] and state['hri']['state'] in ('awaiting_save_confirmation','save_failed'))
        assert state['hri']['state']=='awaiting_save_confirmation',state['hri']
        expected=root/'maps/user_saved'/name.replace(' ','_')
        assert not expected.exists()
        for _ in range(10):gesture.publish(String(data='NONE'));spin(.05)
        gesture.publish(String(data='Thumb_Up'))
        wait(lambda:state['hri']['state'] in ('saved','save_failed'),40)
        assert state['hri']['state']=='saved',state['hri']
        from sys import path
        path.insert(0,str(root/'scripts'))
        from lab_catalog import LabCatalog
        c=LabCatalog(expected/'destinations.yaml')
        report.update(saved_catalog=str(c.path),map_confirmed_by='fresh Thumb_Up',map_hash=c.data['map_sha256'])
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    except Exception as e:error=str(e);raise
    finally:
        control.publish(String(data='stop'))
        (root/'results/mapping_frontier_results.json').write_text(json.dumps(dict(passed=error is None,error=error,results=report,events=events),ensure_ascii=False,indent=2)+'\n')
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
