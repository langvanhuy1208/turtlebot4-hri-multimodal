#!/usr/bin/env python3
"""Real Gazebo motion from voice/gestures; acknowledge ONLY after action success."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lab_catalog import LabCatalog


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    catalog=LabCatalog(args.catalog);ids=list(catalog.regions)[:3]
    rclpy.init();node=Node('direct_hri_gazebo_probe')
    node.set_parameters([Parameter('use_sim_time',value=True)])
    voice=node.create_publisher(String,'/hri/voice',10)
    gesture=node.create_publisher(String,'/detected_gesture',1)
    button=node.create_publisher(String,'/hri/decision',10)
    states,poses,events,results=[],[],[],[]
    def status(msg):
        item=json.loads(msg.data);states.append(item);events.append(item)
        if item['state']!='awaiting_arrival_confirmation':print(msg.data,flush=True)
    def pose(msg):
        q=msg.pose.pose.position;poses.append((q.x,q.y))
    node.create_subscription(String,'/hri/status',status,100)
    node.create_subscription(PoseWithCovarianceStamped,'/amcl_pose',pose,
        QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    def spin(seconds):
        until=time.monotonic()+seconds
        while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.03)
    def wait(predicate,timeout=150):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            rclpy.spin_once(node,timeout_sec=.03)
            if predicate():return
        raise TimeoutError(str(states[-5:]))
    def seen(state,start):return any(s['state']==state for s in states[start:])
    error=None;started=time.monotonic()
    try:
        wait(lambda:voice.get_subscription_count() and gesture.get_subscription_count()
             and button.get_subscription_count() and poses,20)
        for index,rid in enumerate(ids):
            start=len(states)
            button.publish(String(data=json.dumps(dict(action='confirm_arrival',request_id='too-early'))))
            wait(lambda:seen('decision_rejected',start),5)
            start=len(states)
            if index==0:
                voice.publish(String(data='Đi đến '+catalog.regions[rid]['name']))
                source='voice text input'
            else:
                for _ in range(10):gesture.publish(String(data='NONE'));spin(.05)
                label=('Pointing_Up','Victory','Three_Fingers')[index]
                gesture.publish(String(data=label));source='gesture label '+label
            wait(lambda:seen('navigating',start),8)
            assert not seen('awaiting_confirmation',start)
            wait(lambda:seen('completed',start) or seen('failed',start))
            assert not seen('failed',start),states[-8:]
            assert seen('arrived',start) and not seen('awaiting_arrival_confirmation',start)
            goal=catalog.regions[rid]['goal'];distance=math.hypot(poses[-1][0]-goal['x'],poses[-1][1]-goal['y'])
            assert distance<=.5,distance
            results.append(dict(destination=rid,input=source,arrival_error_m=round(distance,3),passed=True,
                                started_without_confirmation=True,automatic_arrival_completion=True))
            print('PASS:',results[-1],flush=True)
    except Exception as exc:error=str(exc);raise
    finally:
        button.publish(String(data=json.dumps(dict(action='stop'))));spin(.2)
        args.output.mkdir(parents=True,exist_ok=True)
        report=dict(source='Actual Gazebo/Nav2/AMCL on saved map',
                    input_note='Automatic text/gesture labels; no arrival confirmation',
                    passed=error is None and len(results)==len(ids),error=error,
                    elapsed_sec=round(time.monotonic()-started,2),results=results,events=events)
        (args.output/'navigation_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()
