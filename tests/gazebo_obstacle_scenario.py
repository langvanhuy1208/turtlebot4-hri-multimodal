#!/usr/bin/env python3
"""Introduce a collision box onto the current Nav2 path and verify replanning."""
import json
import math
from pathlib import Path
import subprocess
import time
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Path as NavPath
from std_msgs.msg import String
from tf2_ros import Buffer,TransformListener
from tf2_msgs.msg import TFMessage


def yaw(q):return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))

def main():
    root=Path(__file__).resolve().parents[1];rclpy.init();n=Node('obstacle_scenario')
    tf=Buffer();listener=TransformListener(tf,n);v=n.create_publisher(String,'/hri/voice',10)
    state={'world':None,'path':None,'nav':None};plans=[];distances=[]
    def pose(m):
        for t in m.transforms:
            if t.child_frame_id=='turtlebot4':state['world']=t.transform
    def plan(m):
        if m.poses:state['path']=m;plans.append(m)
    n.create_subscription(TFMessage,'/simulation/model_poses',pose,10)
    n.create_subscription(NavPath,'/plan',plan,10)
    n.create_subscription(String,'/hri/status',lambda m:state.update(nav=json.loads(m.data)['state']),20)
    def wait(p,timeout=15):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(n,timeout_sec=.03)
            if p():return
        raise TimeoutError(str({k: str(x)[:100] for k,x in state.items()}))
    def move(x,y):
        subprocess.run(['ign','service','-s','/world/lab_slam/remove','--reqtype','ignition.msgs.Entity','--reptype','ignition.msgs.Boolean','--timeout','3000','--req','name: "blocking_box" type: MODEL'],capture_output=True,text=True,timeout=5)
        time.sleep(.3)
        sdf=f'<sdf version="1.8"><model name="blocking_box"><static>true</static><pose>{x} {y} .85 0 0 0</pose><link name="body"><collision name="collision"><geometry><box><size>.7 .7 1.7</size></box></geometry></collision><visual name="visual"><geometry><box><size>.7 .7 1.7</size></box></geometry></visual></link></model></sdf>'
        req='sdf: '+json.dumps(sdf)+' allow_renaming: false'
        r=subprocess.run(['ign','service','-s','/world/lab_slam/create','--reqtype','ignition.msgs.EntityFactory','--reptype','ignition.msgs.Boolean','--timeout','3000','--req',req],capture_output=True,text=True,timeout=5)
        assert 'data: true' in r.stdout,r.stdout+r.stderr
    result={};error=None
    try:
        wait(lambda:state['world'] is not None and v.get_subscription_count())
        v.publish(String(data='Dừng lại'))
        end=time.monotonic()+2
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.03)
        state['path']=None
        wait(lambda:tf.can_transform('map','base_link',rclpy.time.Time()),15)
        v.publish(String(data='Đi đến bàn số 2'));wait(lambda:state['nav']=='navigating' and state['path'] is not None)
        t=tf.lookup_transform('map','base_link',rclpy.time.Time()).transform
        p=state['path'];points=[(q.pose.position.x,q.pose.position.y) for q in p.poses]
        candidates=[q for q in points if 1.4<math.hypot(q[0]-t.translation.x,q[1]-t.translation.y)<1.7]
        assert candidates,'Path too short for obstacle test'
        cx,cy=candidates[len(candidates)//2]
        w=state['world'];theta=yaw(w.rotation)-yaw(t.rotation)
        dx,dy=cx-t.translation.x,cy-t.translation.y
        wx=w.translation.x+math.cos(theta)*dx-math.sin(theta)*dy
        wy=w.translation.y+math.sin(theta)*dx+math.cos(theta)*dy
        before=len(plans);move(wx,wy)
        result.update(box_map_xy=[cx,cy],box_world_xy=[wx,wy])
        print('BOX',result,flush=True)
        def detour():
            for m in plans[before:]:
                distance=min(math.hypot(q.pose.position.x-cx,q.pose.position.y-cy) for q in m.poses)
                distances.append(distance)
                if distance>.40:return True
            return False
        wait(detour,60)
        result['path_avoids_new_box']=True;result['box_map_xy']=[cx,cy]
        wait(lambda:state['nav'] in ('completed','failed'),180)
        assert state['nav']=='completed',state['nav']
        result['arrived_after_replanning']=True
    except Exception as e:error=str(e);raise
    finally:
        v.publish(String(data='Dừng lại'));move(14,10)
        (root/'results/obstacle_gazebo_results.json').write_text(json.dumps(dict(passed=error is None,error=error,results=result,path_clearances=distances[-30:],perception='Actual Gazebo LiDAR and Nav2 obstacle costmap'),ensure_ascii=False,indent=2)+'\n')
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
