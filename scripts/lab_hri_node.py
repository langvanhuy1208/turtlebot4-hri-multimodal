#!/usr/bin/env python3
"""Voice/gesture navigation, clarification, and explicit save transactions."""
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Joy
from action_msgs.msg import GoalStatus
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PointStamped
from visualization_msgs.msg import Marker,MarkerArray
from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener
from rclpy.duration import Duration
from arrival_control import DestinationGestures
from hri_confirmation import ButtonEdges
from interaction_core import Interaction
from lab_catalog import LabCatalog, write_yaml, gesture_slots
from semantic_map import normalize
from voice_navigation_node import VoiceNavigation


class LabHRI(VoiceNavigation):
    def load_catalog(self, filename):
        return LabCatalog(filename)

    def __init__(self):
        super().__init__()
        self.dialogue=Interaction(self.catalog.parse)
        self.manual_requested=False
        self.create_subscription(String,'/session/control',self.session_control,10)
        self.selected_pose=None
        self.selection_pub=self.create_publisher(MarkerArray,'/hri/selected_point',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.catalog_pub=self.create_publisher(String,'/hri/catalog',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.mode_pub=self.create_publisher(String,'/mapping/mode',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(PointStamped,'/clicked_point',self.select_point,10)
        self.create_timer(2.,self.publish_configuration)
        self.voice_busy_until=0.
        self.create_subscription(String,'/hri/listening_state',self.listening_state,10)
        self.tf=Buffer();self.listener=TransformListener(self.tf,self)
        self.save_results=queue.Queue()
        self.saving=False
        self.resume_route=None;self.pause_waiting=False;self.safety_state='clear'
        self.create_subscription(String,'/hri/safety',self.safety,10)
        self.odom_at=-1e9;self.moving=True
        self.create_subscription(Odometry,'odom',self.odometry,qos_profile_sensor_data)
        self.mapping_state='manual'
        self.create_subscription(String,'/mapping/mode',lambda m:setattr(self,'mapping_state',m.data),10)
        self.mapping_pub=self.create_publisher(String,'/mapping/control',10)
        for key,value in [('require_localization',True),('require_stationary_save',True),('mapping_session',False),('enable_hmi_buttons',False),('enable_joy_buttons',False),
                          ('confirm_button',0),('cancel_button',1),
                          ('gesture_destinations',self.catalog.data.get('gesture_destinations',list(self.catalog.regions)[:3]) or ['unconfigured'])]:
            self.declare_parameter(key,value)
        destinations=list(self.get_parameter('gesture_destinations').value)
        self.gestures=DestinationGestures(destinations)
        self.button_edges=ButtonEdges()
        self.confirm_index=self.get_parameter('confirm_button').value
        self.cancel_index=self.get_parameter('cancel_button').value
        if min(self.confirm_index,self.cancel_index)<0 or self.confirm_index==self.cancel_index:
            raise ValueError('Chỉ số nút xác nhận/hủy phải khác nhau và >= 0')
        self.create_subscription(String,'/hri/decision',self.decision,10)
        self.create_subscription(String,'/detected_gesture',self.gesture,1)
        if self.get_parameter('enable_joy_buttons').value:
            self.create_subscription(Joy,'/joy',lambda m:self.buttons(m.buttons),1)
        if self.get_parameter('enable_hmi_buttons').value:
            if self.get_parameter('enable_joy_buttons').value:raise ValueError('Chỉ chọn một nguồn nút')
            from turtlebot4_msgs.msg import UserButton
            self.create_subscription(UserButton,'/hmi/buttons',lambda m:self.buttons(m.button),1)
        self.publish_configuration()
        self.status('ready',regions=list(self.catalog.regions),gesture_destinations=self.gestures.mapping)

    def status(self,state,**fields):
        region=fields.get('region')
        if region and region in self.catalog.regions:
            fields.setdefault('destination',self.catalog.regions[region]['name'])
        if state=='arrived':fields['prompt']='Đã đến '+fields.get('destination',region or '')
        super().status(state,**fields)

    def listening_state(self,msg):
        now=time.monotonic()
        if msg.data in ('speech','transcribing'):
            self.voice_busy_until=now+12
            if self.dialogue.candidate:self.dialogue.candidate['deadline']=max(self.dialogue.candidate['deadline'],self.voice_busy_until)
        elif msg.data in ('listening','error','done'):
            self.voice_busy_until=0.
            if self.dialogue.candidate:self.dialogue.candidate['deadline']=min(self.dialogue.candidate['deadline'],now+.2)

    def command(self,msg):
        self.process(self.dialogue.input(msg.data,'voice',time.monotonic()))

    def process(self,events):
        for e in events:
            e=dict(e);state=e.pop('state')
            if state=='stop':
                if not self.get_parameter('mapping_session').value:self.mode_pub.publish(String(data='stop'))
                self.resume_route=None
                if self.pause_waiting:
                    self.pause_waiting=False;self.finish('cancelled');continue
                if self.get_parameter('mapping_session').value:self.mapping_pub.publish(String(data='stop'))
                VoiceNavigation.command(self,String(data='Dừng lại'))
            elif state=='mapping_mode':
                if self.get_parameter('mapping_session').value:self.mapping_pub.publish(String(data=e['mode']))
                else:self.status('rejected',reason='Hãy mở phiên quét bản đồ trước.')
            elif state=='navigate':
                if self.resume_route:
                    self.status('rejected',reason='Đang chờ vùng an toàn. Nói dừng lại trước khi đổi đích.');continue
                if self.get_parameter('mapping_session').value:self.status('rejected',reason='Đang quét map. Lưu map và chuyển sang điều hướng trước.');continue
                if self.saving:self.status('rejected',reason='Đang lưu dữ liệu');continue
                try:
                    self.catalog=LabCatalog(self.catalog.path);self.dialogue.resolve_route=self.catalog.parse
                    if self.get_parameter('require_localization').value:self.localized_pose()
                    if not self.busy:self.mode_pub.publish(String(data='navigation'))
                    VoiceNavigation.command(self,String(data='Đi đến '+' rồi đến '.join(e['route'])))
                except Exception as exc:self.status('rejected',reason=str(exc))
            elif state=='prepare_save':
                self.prepare_save(e['operation'],e['name'],e.get('target'))
            elif state=='commit_save':
                self.commit_save(e)
            else:self.status(state,**e)

    def safety(self,msg):
        try:state=json.loads(msg.data)['state']
        except (ValueError,KeyError):return
        self.safety_state=state
        if state in ('person_stop','obstacle_stop','sensor_stale','waiting_clear'):
            if self.busy and not self.cancel_requested and self.resume_route is None:
                self.resume_route=[self.current,*self.queue]
                self.deadline=None
                self.status('waiting_safety',reason=state,prompt='Robot dừng chờ vùng an toàn; sẽ tiếp tục khi đủ điều kiện.')
                self.cancel_active()
        elif state in ('clear','person_warning','command_stale'):
            self.resume_safely()

    def goal_response(self,future):
        super().goal_response(future)
        if self.resume_route and self.goal_handle:self.cancel_active()

    def goal_result(self,future):
        if self.resume_route and not self.cancel_requested:
            try:code=future.result().status
            except Exception as exc:self.finish('failed',reason=str(exc));return
            self.goal_handle=None;self.cancel_sent=False;self.deadline=None
            if code==GoalStatus.STATUS_SUCCEEDED:
                self.status('arrived',region=self.current)
                self.resume_route=list(self.queue)
            if not self.resume_route:self.finish('completed');return
            self.pause_waiting=True
            self.status('paused_safety',prompt='Đang chờ vùng an toàn để tiếp tục hành trình.')
            self.resume_safely()
            return
        super().goal_result(future)

    def resume_safely(self):
        if not self.pause_waiting or self.safety_state not in ('clear','person_warning','command_stale'):return
        route=self.resume_route
        self.resume_route=None;self.pause_waiting=False;self.busy=False
        self.status('resuming',prompt='Vùng an toàn đã trống. Robot tiếp tục hành trình.')
        VoiceNavigation.command(self,String(data='Đi đến '+' rồi đến '.join(route)))

    def session_control(self,msg):
        if self.get_parameter('mapping_session').value:return
        if msg.data=='manual':
            self.manual_requested=True
            self.command(String(data='Dừng lại'))
            if not self.busy:
                self.manual_requested=False;self.mode_pub.publish(String(data='manual'))
        elif msg.data=='navigation' and not self.busy:self.mode_pub.publish(String(data='navigation'))

    def finish(self,state,**fields):
        self.resume_route=None;self.pause_waiting=False
        super().finish(state,**fields)
        if getattr(self,'manual_requested',False):
            self.manual_requested=False;self.mode_pub.publish(String(data='manual'))

    def odometry(self,msg):
        self.odom_at=time.monotonic()
        t=msg.twist.twist
        self.moving=abs(t.linear.x)>.02 or abs(t.linear.y)>.02 or abs(t.angular.z)>.05

    def check_stationary(self):
        if self.get_parameter('require_stationary_save').value and (self.moving or time.monotonic()-self.odom_at>1):
            raise ValueError('Chưa xác nhận robot đứng yên hoặc odom đã cũ. Dừng robot trước khi lưu.')

    def localized_pose(self):
        t=self.tf.lookup_transform('map','base_link',rclpy.time.Time(),timeout=Duration(seconds=0))
        age=(self.get_clock().now()-rclpy.time.Time.from_msg(t.header.stamp)).nanoseconds/1e9
        if not 0<=age<=1.5:raise ValueError('Định vị đã cũ; hãy định vị robot trước.')
        return t

    def ready_to_save(self):
        try:
            self.check_stationary()
            if self.get_parameter('require_localization').value:self.localized_pose()
            return True
        except Exception:return False

    def publish_configuration(self):
        if not hasattr(self,'gestures'):return
        self.catalog_pub.publish(String(data=json.dumps(dict(mapping_session=self.get_parameter('mapping_session').value,
            ready_to_save=self.ready_to_save(),map_name=self.catalog.path.parent.name,places=list(self.catalog.regions.values()),
            gesture_destinations=self.gestures.mapping),ensure_ascii=False)))

    def select_point(self,msg):
        try:
            if self.get_parameter('mapping_session').value:raise ValueError('Lưu map xong trước khi chọn địa điểm.')
            if msg.header.frame_id!=self.catalog.data['frame_id']:raise ValueError('Điểm chọn không nằm trong hệ tọa độ map đang dùng.')
            pose=dict(x=float(msg.point.x),y=float(msg.point.y),yaw=0.)
            self.catalog.validate_pose(**pose)
            self.selected_pose=dict(pose=pose,map_hash=self.catalog.map.fingerprint())
            marker=Marker();marker.header=msg.header;marker.ns='hri_selected_point';marker.id=0;marker.type=Marker.SPHERE;marker.action=Marker.ADD
            marker.pose.position=msg.point;marker.pose.position.z=.12;marker.pose.orientation.w=1.
            marker.scale.x=marker.scale.y=marker.scale.z=.25;marker.color.g=marker.color.b=marker.color.a=1.
            self.selection_pub.publish(MarkerArray(markers=[marker]))
            self.status('point_selected',pose=pose,prompt='Đã chọn điểm. Nhập tên rồi bấm LƯU ĐIỂM ĐÃ CHỌN; xác nhận để lưu.')
        except Exception as exc:
            self.selected_pose=None
            marker=Marker();marker.header.frame_id='map';marker.action=Marker.DELETEALL;self.selection_pub.publish(MarkerArray(markers=[marker]))
            self.status('save_failed',reason=str(exc))

    def prepare_save(self,operation,name,target=None):
        if self.busy or self.saving or (self.get_parameter('mapping_session').value and self.mapping_state=='auto'):
            self.status('rejected',reason='Hãy dừng robot và chờ dừng xong trước khi lưu.');return
        try:
            self.check_stationary()
            selected=operation=='save_selected_place'
            if selected:operation='save_place'
            self.catalog=LabCatalog(self.catalog.path) # reject externally changed map
            if not name or len(name)>60:raise ValueError('Tên phải dài từ 1 đến 60 ký tự')
            payload={}
            if operation=='save_map':
                t=self.tf.lookup_transform('map','odom',rclpy.time.Time()).transform
                q=t.rotation
                payload['spawn_initial_pose']=dict(x=t.translation.x,y=t.translation.y,yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
            if operation=='alias_place':
                if target not in self.catalog.regions:raise ValueError('Không có địa điểm gốc')
                if normalize(name) in self.catalog.aliases:raise ValueError('Tên gọi này đã được sử dụng')
                payload['rid']=target
            elif operation!='save_map':
                if self.get_parameter('mapping_session').value:raise ValueError('Lưu map xong và mở map đã lưu trước khi dạy địa điểm.')
                key=normalize(name);rid=self.catalog.aliases.get(key)
                if operation=='save_place' and rid:raise ValueError('Tên đã có. Nói cập nhật địa điểm '+name+' để thay vị trí.')
                if operation in ('update_place','delete_place') and not rid:raise ValueError('Chưa có địa điểm này.')
                payload['rid']=rid or key.replace(' ','_')
                if operation!='delete_place':
                    if selected:
                        if not self.selected_pose or self.selected_pose['map_hash']!=self.catalog.map.fingerprint():raise ValueError('Hãy chọn lại điểm trên map đang dùng.')
                        pose=dict(self.selected_pose['pose'])
                    else:
                        t=self.localized_pose()
                        p=t.transform.translation;q=t.transform.rotation
                        pose=dict(x=p.x,y=p.y,yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
                    self.catalog.validate_pose(**pose);payload['pose']=pose
            self.status(**self.dialogue.prepare(operation,name,time.monotonic(),**payload))
        except Exception as exc:self.status('save_failed',reason=str(exc))

    def commit_save(self,e):
        if self.busy or self.saving or (self.get_parameter('mapping_session').value and self.mapping_state=='auto'):
            self.status('save_failed',reason='Robot đang bận; yêu cầu lưu đã hủy.');return
        try:
            self.check_stationary()
            catalog=LabCatalog(self.catalog.path)
            if e['operation']=='save_map':
                folder=Path(__file__).resolve().parents[1]/'maps'/'user_saved'/normalize(e['name']).replace(' ','_')
                if folder.exists():raise ValueError('Tên bản đồ đã tồn tại; chọn tên khác.')
                folder.mkdir(parents=True)
                self.saving=True
                def save():
                    try:
                        result=subprocess.run(['ros2','run','nav2_map_server','map_saver_cli','-f',str(folder/'map'),
                            '--ros-args','-r','__ns:='+self.get_namespace(),'-p','use_sim_time:='+str(self.get_parameter('use_sim_time').value).lower()],
                            capture_output=True,text=True,timeout=25)
                        if result.returncode:raise RuntimeError(result.stderr[-500:])
                        from semantic_map import OccupancyMap
                        snapshot=OccupancyMap(folder/'map.yaml')
                        data=dict(catalog.data);data['map']='map.yaml';data['map_sha256']=snapshot.fingerprint()
                        # Validate every old coordinate against this snapshot; never silently migrate invalid points.
                        try:write_yaml(folder/'destinations.yaml',data)
                        except ValueError:
                            data['regions']=[];write_yaml(folder/'destinations.yaml',data)
                            (folder/'old_destinations_review.yaml').write_text(__import__('yaml').safe_dump(catalog.data,allow_unicode=True))
                        (folder/'map_metadata.json').write_text(json.dumps(dict(name=e['name'],spawn_initial_pose=e['spawn_initial_pose'],note='Simulation spawn alignment only. Real deployment needs actual initial localization.'),ensure_ascii=False,indent=2)+'\n')
                        root=Path(__file__).resolve().parents[1]
                        (root/'results/latest_user_map.txt').write_text(str(folder)+'\n')
                        self.save_results.put(dict(state='saved',prompt='Đã lưu bản đồ '+e['name'],path=str(folder)))
                    except Exception as exc:self.save_results.put(dict(state='save_failed',reason=str(exc)))
                threading.Thread(target=save,daemon=True).start();self.status('saving',prompt='Đang lưu bản đồ');return
            rid=e['rid'];data=catalog.data
            if e['operation']=='alias_place':
                data['regions']=[dict(r,aliases=[*r.get('aliases',[]),e['name']]) if r['id']==rid else r for r in data['regions']]
                write_yaml(catalog.path,data);self.catalog=LabCatalog(catalog.path);self.dialogue.resolve_route=self.catalog.parse
                self.publish_configuration();self.status('saved',prompt='Đã học tên gọi '+e['name']);return
            data['regions']=[r for r in data['regions'] if r['id']!=rid]
            if e['operation']!='delete_place':
                old=catalog.regions.get(rid,{})
                data['regions'].append(dict(id=rid,name=old.get('name',e['name']),aliases=old.get('aliases',[]),goal=e['pose']))
            data['gesture_destinations']=gesture_slots([r['id'] for r in data['regions']],self.gestures.mapping.values())
            write_yaml(catalog.path,data)
            self.catalog=LabCatalog(catalog.path);self.dialogue.resolve_route=self.catalog.parse
            self.gestures=DestinationGestures(data['gesture_destinations'])
            self.publish_regions();self.publish_configuration();self.status('saved',gesture_destinations=self.gestures.mapping,prompt='Đã lưu thay đổi địa điểm '+e['name'])
        except Exception as exc:self.status('save_failed',reason=str(exc))

    def decision(self,msg):
        try:
            data=json.loads(msg.data)
            if data.get('action')=='confirm_save' and isinstance(data.get('request_id'),str):self.process(self.dialogue.confirm(data.get('request_id'),time.monotonic()))
            elif data.get('action')=='prepare_selected_place':self.prepare_save('save_selected_place',str(data.get('name','')))
            elif data.get('action') in ('stop','cancel'):self.command(String(data='Dừng lại'))
            else:raise ValueError('Chỉ xác nhận khi lưu bản đồ hoặc địa điểm; đến đích tự hoàn thành.')
        except (ValueError,TypeError,AttributeError) as exc:self.status('decision_rejected',reason=str(exc))

    def gesture(self,msg):
        destination=self.gestures.receive(msg.data,time.monotonic())
        if msg.data=='AMBIGUOUS':
            self.dialogue.candidate=None
            self.status('clarify',prompt='Camera thấy nhiều bàn tay. Chỉ một người đưa một tay vào khung điều khiển.');return
        if msg.data in ('Open_Palm','Closed_Fist'):self.command(String(data='Dừng lại'))
        elif self.gestures.confirmation_event:self.process(self.dialogue.confirm(None,time.monotonic()))
        elif destination:
            if destination not in self.catalog.regions:self.status('rejected',reason='Chưa gán địa điểm cho cử chỉ');return
            self.process(self.dialogue.input('Đi đến '+destination,'gesture',time.monotonic()))
            if self.dialogue.candidate and time.monotonic()<self.voice_busy_until:
                self.dialogue.candidate['deadline']=max(self.dialogue.candidate['deadline'],self.voice_busy_until)

    def buttons(self,values):
        rising=self.button_edges.update(values)
        if self.cancel_index in rising:self.command(String(data='Dừng lại'))
        elif self.confirm_index in rising:self.process(self.dialogue.confirm(None,time.monotonic()))

    def tick(self):
        super().tick()
        if not hasattr(self,'dialogue'):return
        now=time.monotonic();self.process(self.dialogue.flush(now)+self.dialogue.expire(now))
        while not self.save_results.empty():
            self.saving=False;self.status(**self.save_results.get())


def main(args=None):
    rclpy.init(args=args);node=None
    try:node=LabHRI();rclpy.spin(node)
    except KeyboardInterrupt:
        if node and node.busy:
            node.command(String(data='Dừng lại'));until=time.monotonic()+3
            while node.busy and time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.1)
    finally:
        if node:node.destroy_node()
        if rclpy.ok():rclpy.shutdown()

if __name__=='__main__':main()
