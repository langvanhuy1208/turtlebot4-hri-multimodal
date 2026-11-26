#!/usr/bin/env python3
"""Move real collision bodies in Gazebo while Nav2 drives; observe final velocity."""
import json
import math
from pathlib import Path
import subprocess
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from tf2_msgs.msg import TFMessage


def main():
    root=Path(__file__).resolve().parents[1];rclpy.init();n=Node('people_scenario_probe')
    voice=n.create_publisher(String,'/hri/voice',10)
    state={'robot':None,'safety':None,'velocity':0.,'navigation':None};events=[]
    def pose(m):
        for t in m.transforms:
            if t.child_frame_id=='turtlebot4':state['robot']=(t.transform.translation.x,t.transform.translation.y)
    def safety(m):
        d=json.loads(m.data);state['safety']=d['state'];events.append(d)
    def nav(m):state['navigation']=json.loads(m.data)['state']
    n.create_subscription(TFMessage,'/simulation/model_poses',pose,10)
    n.create_subscription(String,'/hri/safety',safety,10)
    n.create_subscription(String,'/hri/status',nav,10)
    n.create_subscription(Twist,'/cmd_vel',lambda m:state.update(velocity=abs(m.linear.x)+abs(m.angular.z)),10)
    def wait(p,timeout=30):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(n,timeout_sec=.03)
            if p():return
        raise TimeoutError(str(state))
    def spin(t):
        end=time.monotonic()+t
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.03)
    def move(name,x,y):
        req=f'name: "{name}" position: {{x: {x} y: {y} z: 0.85}} orientation: {{w: 1}}'
        r=subprocess.run(['ign','service','-s','/world/lab_slam/set_pose','--reqtype','ignition.msgs.Pose','--reptype','ignition.msgs.Boolean','--timeout','3000','--req',req],capture_output=True,text=True,timeout=5)
        if 'data: true' not in r.stdout:raise RuntimeError(r.stdout+r.stderr)
    checks=[];error=None
    try:
        wait(lambda:state['robot'] is not None and voice.get_subscription_count()>0)
        voice.publish(String(data='Đi đến bàn số 2'))
        wait(lambda:state['navigation']=='navigating');wait(lambda:state['velocity']>.05)
        x,y=state['robot'];move('person_1',x+1.1,y)
        wait(lambda:state['safety']=='person_warning',10);checks.append('Nearby person causes warning and reduced velocity')
        x,y=state['robot'];move('person_1',x+.65,y)
        wait(lambda:state['safety']=='person_stop',10);spin(.3)
        assert state['velocity']<1e-6,state
        spin(2);assert state['velocity']<1e-6
        checks.append('Stationary person remains human; final velocity stays zero')
        move('person_1',10,10)
        wait(lambda:state['safety']=='clear',10);wait(lambda:state['velocity']>.01,10)
        checks.append('Clear zone held stable before navigation resumes')
        wait(lambda:state['navigation'] in ('completed','failed'),150)
        assert state['navigation']=='completed',state
        checks.append('Original Nav2 destination completes after person leaves')
    except Exception as e:error=str(e);raise
    finally:
        voice.publish(String(data='Dừng lại'))
        move('person_1',10,10);spin(.3)
        (root/'results/people_gazebo_results.json').write_text(json.dumps(dict(passed=error is None,error=error,checks=checks,events=events,perception='Gazebo semantic ground truth, not camera inference'),ensure_ascii=False,indent=2)+'\n')
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
