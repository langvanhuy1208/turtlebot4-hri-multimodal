#!/usr/bin/env python3
"""Real Gazebo end-to-end session handover and arbitrary location placement."""
import json
import math
from pathlib import Path
import sys
import time
import rclpy
from geometry_msgs.msg import PointStamped,Twist
from nav_msgs.msg import Odometry
from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String
from tf2_ros import Buffer,TransformListener
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from lab_catalog import LabCatalog


def main():
    rclpy.init();n=rclpy.create_node('session_workflow_test');n.set_parameters([rclpy.parameter.Parameter('use_sim_time',value=True)])
    tf=Buffer();listener=TransformListener(tf,n)
    v=n.create_publisher(String,'/hri/voice',10);g=n.create_publisher(String,'/detected_gesture',10)
    c=n.create_publisher(String,'/mapping/control',10);m=n.create_publisher(Twist,'/cmd_vel_manual',10)
    points=n.create_publisher(PointStamped,'/clicked_point',10);decisions=n.create_publisher(String,'/hri/decision',10)
    states=[];data={'mode':None,'odom':None,'catalog':None}
    n.create_subscription(String,'/hri/status',lambda msg:states.append(json.loads(msg.data)),100)
    n.create_subscription(String,'/mapping/mode',lambda msg:data.update(mode=msg.data),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    n.create_subscription(String,'/hri/catalog',lambda msg:data.update(catalog=json.loads(msg.data)),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    n.create_subscription(Odometry,'/odom',lambda msg:data.update(odom=msg.pose.pose.position),10)
    def spin(t):
        end=time.monotonic()+t
        while time.monotonic()<end:rclpy.spin_once(n,timeout_sec=.03)
    def wait(p,timeout=40):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(n,timeout_sec=.03)
            if p():return
        raise TimeoutError(str(states[-6:]))
    def seen(state,start):return any(s['state']==state for s in states[start:])
    def command(text,state,timeout=40):
        start=len(states);v.publish(String(data=text));wait(lambda:seen(state,start),timeout);return start
    error=None;checks=[];report={};name='phien moi '+time.strftime('%Y%m%d %H%M%S')
    try:
        wait(lambda:data['catalog'] and data['catalog']['mapping_session'] and v.get_subscription_count() and data['odom'],120)
        checks.append('Fresh SLAM session has no fixed destinations')
        assert not data['catalog']['places']
        c.publish(String(data='manual'));wait(lambda:data['mode']=='manual')
        startxy=(data['odom'].x,data['odom'].y);vel=Twist();vel.linear.x=.1
        move_until=time.monotonic()+25
        while math.hypot(data['odom'].x-startxy[0],data['odom'].y-startxy[1])<.08:
            m.publish(vel);spin(.05)
            if time.monotonic()>move_until:raise TimeoutError('Manual mapping motion did not progress')
        m.publish(Twist());spin(.5)
        travel=math.hypot(data['odom'].x-startxy[0],data['odom'].y-startxy[1]);assert travel>.025,travel
        report['manual_travel_m']=travel;checks.append('Manual input moves robot through safety gate during SLAM')
        c.publish(String(data='stop'));wait(lambda:data['mode']=='stop');spin(2)
        command('Lưu bản đồ '+name,'awaiting_save_confirmation')
        start=command('Xác nhận','saved')
        saved=next(s['path'] for s in states[start:] if s['state']=='saved' and s.get('path'))
        folder=Path(saved);LabCatalog(folder/'destinations.yaml');report['catalog']=str(folder/'destinations.yaml')
        checks.append('Explicit map save confirmation writes real SLAM image and empty catalog')
        wait(lambda:data['catalog'] and not data['catalog']['mapping_session'] and data['catalog'].get('ready_to_save',False) and seen('session_ready',start),100)
        checks.append('Same world automatically switches SLAM to AMCL; destination editor enabled')
        command('Lưu địa điểm điểm bắt đầu','awaiting_save_confirmation');command('Xác nhận','saved')
        cat=LabCatalog(folder/'destinations.yaml');assert 'diem_bat_dau' in cat.regions
        checks.append('Teach current robot position after handover')
        wait(lambda:tf.can_transform('map','base_link',rclpy.time.Time()),20)
        t=tf.lookup_transform('map','base_link',rclpy.time.Time()).transform
        xy=(t.translation.x,t.translation.y);selected=None
        for dx,dy in [(1.,0.),(-1.,0.),(0.,1.),(0.,-1.),(.7,.7),(-.7,-.7)]:
            try:cat.validate_pose(xy[0]+dx,xy[1]+dy,0.)
            except ValueError:continue
            selected=(xy[0]+dx,xy[1]+dy);break
        assert selected is not None
        point=PointStamped();point.header.frame_id='map';point.point.x,point.point.y=selected
        start=len(states);points.publish(point);wait(lambda:seen('point_selected',start))
        spin(.5);assert not seen('navigating',start)
        decisions.publish(String(data=json.dumps(dict(action='prepare_selected_place',name='điểm chọn trên map'))))
        wait(lambda:seen('awaiting_save_confirmation',start));assert 'diem_chon_tren_map' not in LabCatalog(folder/'destinations.yaml').regions
        command('Xác nhận','saved')
        saved_goal=LabCatalog(folder/'destinations.yaml').regions['diem_chon_tren_map']['goal']
        assert math.hypot(saved_goal['x']-selected[0],saved_goal['y']-selected[1])<1e-6
        report['selected_xy']=selected;checks.append('RViz-selected coordinate is named and saved only after confirmation')
        start=len(states)
        for _ in range(10):g.publish(String(data='NONE'));spin(.05)
        g.publish(String(data='Victory'))
        wait(lambda:seen('navigating',start),10);wait(lambda:seen('completed',start) or seen('failed',start),100)
        assert seen('completed',start) and not seen('failed',start),states[-6:]
        assert not seen('awaiting_arrival_confirmation',start)
        checks.append('Second finger slot immediately navigates to user-selected place with automatic arrival')
    except Exception as e:error=str(e);raise
    finally:
        v.publish(String(data='Dừng lại'));m.publish(Twist());spin(.2)
        (ROOT/'results/session_workflow_results.json').write_text(json.dumps(dict(passed=error is None,error=error,checks=checks,results=report,events=states),ensure_ascii=False,indent=2)+'\n')
        n.destroy_node();rclpy.shutdown()
if __name__=='__main__':main()
