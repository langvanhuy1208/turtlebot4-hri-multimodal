#!/usr/bin/env python3
"""Own the scan -> confirmed save -> AMCL -> teach arbitrary places session."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import yaml
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile,DurabilityPolicy,qos_profile_sensor_data
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid,Odometry
from std_msgs.msg import String
from tf2_ros import Buffer,TransformListener
from lab_catalog import create_catalog,LabCatalog
import session_storage as storage

ROOT=Path(__file__).resolve().parents[1]


def yaw(q):return math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))


class Session(Node):
    def __init__(self,args,runtime):
        ns=args.namespace.strip('/')
        prefix='/'+ns if ns else ''
        super().__init__('project_session',namespace=prefix,cli_args=['--ros-args','-r','/tf:='+prefix+'/tf','-r','/tf_static:='+prefix+'/tf_static'])
        self.args=args;self.runtime=runtime;self.children={};self.files=[]
        self.set_parameters([rclpy.parameter.Parameter('use_sim_time',value=args.mode=='sim')])
        self.tf=Buffer();self.listener=TransformListener(self.tf,self)
        self.phase='starting';self.map=None;self.amcl=None;self.odom=None;self.mode=None;self.saved=None;self.hri_configuration=None
        self.checkpoint_due=False;self.checkpoint_signature=None;self.hri_state=None;self.catalog_switch=None
        self.map_pub=self.create_publisher(String,'hri/status',10)
        self.control=self.create_publisher(String,'mapping/control',10)
        self.mode_pub=self.create_publisher(String,'mapping/mode',QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.initial=self.create_publisher(PoseWithCovarianceStamped,'initialpose',10)
        self.create_subscription(OccupancyGrid,'map',lambda m:setattr(self,'map',m),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(Odometry,'odom',lambda m:setattr(self,'odom',m),qos_profile_sensor_data)
        self.create_subscription(PoseWithCovarianceStamped,'amcl_pose',lambda m:setattr(self,'amcl',m),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(String,'mapping/mode',self.mapping_mode,QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(String,'hri/catalog',lambda m:setattr(self,'hri_configuration',json.loads(m.data)),QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(String,'mapping/status',self.mapping_status,20)
        self.create_subscription(String,'hri/status',self.status,20)
        self.report=dict(mode=args.mode,scene=args.scene,namespace=ns,phases=[])

    def status(self,msg):
        try:
            d=json.loads(msg.data);self.hri_state=d['state']
            if self.phase=='mapping' and d['state']=='saving':self.control.publish(String(data='stop'))
            if self.phase in ('mapping','navigation') and d['state']=='saved' and d.get('path'):
                path=Path(d['path']).resolve()
                if path.is_relative_to(ROOT/'maps/user_saved'):
                    LabCatalog(path/'destinations.yaml')
                    if self.phase=='mapping':
                        self.saved=path;self.remember_map(path/'destinations.yaml')
                    else:self.catalog_switch=path
        except (ValueError,KeyError,OSError) as e:self.get_logger().warning(str(e))

    def map_context(self):return storage.context(self.args.mode,self.args.scene,self.args.namespace)

    def remember_map(self,catalog):
        meta=Path(catalog).parent/'map_metadata.json'
        data=json.loads(meta.read_text()) if meta.exists() else {}
        data['context']=self.map_context();storage.atomic_json(meta,data)
        storage.remember(ROOT,catalog,self.map_context())

    def mapping_mode(self,msg):
        if self.phase=='mapping' and self.mode in ('auto','manual') and msg.data=='stop':self.checkpoint_due=True
        self.mode=msg.data

    def mapping_status(self,msg):
        try:
            if self.phase=='mapping' and json.loads(msg.data)['state'] in ('exploration_finished','limit_reached'):
                self.checkpoint_due=True;self.control.publish(String(data='stop'))
        except (ValueError,KeyError):pass

    def maybe_checkpoint(self):
        if self.phase!='mapping' or not self.checkpoint_due or self.saved or self.mode!='stop' or not self.stationary():return
        if self.hri_state in ('awaiting_save_confirmation','saving'):return
        self.checkpoint_due=False
        try:
            m=self.map
            if m is None:return
            signature=hash((bytes(np.asarray(m.data,dtype=np.int8)),m.info.width,m.info.height,m.info.origin.position.x,m.info.origin.position.y))
            if signature==self.checkpoint_signature:return
            t=self.tf.lookup_transform('map','odom',rclpy.time.Time()).transform
            file=storage.recovery(ROOT,self.map_context(),np.array(m.data).reshape(m.info.height,m.info.width),m.info.resolution,
                (m.info.origin.position.x,m.info.origin.position.y,yaw(m.info.origin.orientation)),dict(x=t.translation.x,y=t.translation.y,yaw=yaw(t.rotation)))
            self.checkpoint_signature=signature;self.report['recovery_catalog']=str(file)
            self.publish('recovery_saved','Đã tự lưu map phục hồi. Lần sau có thể mở lại; đặt tên map và xác nhận để hoàn tất phiên quét.')
        except Exception as e:self.publish('recovery_failed','Chưa tự lưu được map: '+str(e))

    def maybe_switch_catalog(self):
        if self.phase!='navigation' or self.catalog_switch is None or not self.stationary():return
        if self.hri_state in ('accepted','navigating','waiting_safety','paused_safety','cancelling'):return
        folder=self.catalog_switch;self.catalog_switch=None
        catalog=LabCatalog(folder/'destinations.yaml')
        if not self.map_matches(catalog):
            self.publish('snapshot_saved','Đã lưu map khác. Chọn --catalog để mở map đó ở phiên sau.');return
        self.mode_pub.publish(String(data='stop'));self.stop('hri');self.hri_configuration=None
        self.component('hri','hri',catalog=str(catalog.path),mapping_session='false')
        self.wait(lambda:self.hri_configuration is not None and self.hri_configuration.get('map_name')==folder.name and self.hri_configuration.get('ready_to_save',False),25)
        self.saved=folder;self.remember_map(catalog.path);self.report['catalog']=str(catalog.path)
        self.mode_pub.publish(String(data='navigation'))
        self.publish('session_ready','Đã dùng map vừa lưu. Các địa điểm mới sẽ được ghi vào map này.')

    def publish(self,state,prompt):
        self.map_pub.publish(String(data=json.dumps(dict(state=state,prompt=prompt),ensure_ascii=False)))
        self.get_logger().info(prompt)
        self.report['phases'].append(dict(state=state,time_unix=time.time()))
        (self.runtime/'session_report.json').write_text(json.dumps(self.report,ensure_ascii=False,indent=2)+'\n')

    def start(self,key,cmd):
        if key in self.children:raise RuntimeError('Component already running: '+key)
        log=(self.runtime/(key+'.log')).open('a');self.files.append(log)
        child_env=os.environ.copy()
        for variable in ('QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_FONTDIR'):
            if 'cv2' in child_env.get(variable,''):child_env.pop(variable,None)
        if key=='gazebo_gui':child_env['IGN_GAZEBO_RESOURCE_PATH']=str(ROOT/'worlds')+':/opt/ros/humble/share'
        self.children[key]=subprocess.Popen(cmd,cwd=ROOT,env=child_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)

    def component(self,key,role,**kwargs):
        fields=dict(component=role,namespace=self.args.namespace,use_sim_time=str(self.args.mode=='sim').lower(),scene=self.args.scene,profile=self.args.profile,**kwargs)
        self.start(key,['ros2','launch','tb4_cuoiky','session_components.launch.py',*[k+':='+str(v) for k,v in fields.items() if str(v)]])

    def stop(self,key):
        p=self.children.pop(key,None)
        if p is None:return
        for sig,delay in [(signal.SIGINT,3),(signal.SIGTERM,2),(signal.SIGKILL,1)]:
            try:os.killpg(p.pid,sig)
            except ProcessLookupError:break
            try:p.wait(timeout=delay);break
            except subprocess.TimeoutExpired:continue

    def wait(self,predicate,timeout=None):
        end=time.monotonic()+timeout if timeout else float('inf')
        while rclpy.ok() and not predicate():
            rclpy.spin_once(self,timeout_sec=.05)
            self.maybe_checkpoint()
            self.maybe_switch_catalog()
            for key in ('world','slam','nav','hri'):
                if key in self.children and self.children[key].poll() is not None:raise RuntimeError(key+' stopped; see '+str(self.runtime/(key+'.log')))
            if time.monotonic()>end:raise TimeoutError('Session '+self.phase+' timed out; logs: '+str(self.runtime))
        if not rclpy.ok():raise KeyboardInterrupt

    def stationary(self):
        if not self.odom:return False
        age=(self.get_clock().now()-rclpy.time.Time.from_msg(self.odom.header.stamp)).nanoseconds/1e9
        t=self.odom.twist.twist
        return 0<=age<1 and abs(t.linear.x)<.02 and abs(t.linear.y)<.02 and abs(t.angular.z)<.05

    def map_matches(self,catalog):
        if self.map is None:return False
        m=self.map;o=catalog.map
        if (m.info.width,m.info.height)!=(o.width,o.height) or abs(m.info.resolution-o.resolution)>1e-6:return False
        if abs(m.info.origin.position.x-o.origin[0])>1e-6 or abs(m.info.origin.position.y-o.origin[1])>1e-6:return False
        actual=np.asarray(m.data).reshape(o.height,o.width)[::-1]
        occupancy=o.image.astype(float)/255
        if not o.meta.get('negate',0):occupancy=1-occupancy
        expected=np.full(o.image.shape,-1,dtype=np.int16);expected[occupancy<float(o.meta['free_thresh'])]=0;expected[occupancy>float(o.meta['occupied_thresh'])]=100
        return np.array_equal(actual,expected)

    def start_rviz(self):
        config=yaml.safe_load((ROOT/'config'/('nav_maze.rviz' if self.args.scene=='maze' else 'nav_voice.rviz')).read_text())
        if self.map is not None:
            m=self.map;view=config['Visualization Manager']['Views']['Current']
            view.update(X=m.info.origin.position.x+m.info.width*m.info.resolution/2,Y=m.info.origin.position.y+m.info.height*m.info.resolution/2,Scale=min(90.,800/max(1.,m.info.width*m.info.resolution),650/max(1.,m.info.height*m.info.resolution)))
        file=self.runtime/'session_view.rviz';file.write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
        self.component('rviz','rviz',rviz_config=str(file))

    def run(self):
        self.publish('session_starting','Đang mở dự án và kiểm tra map đã lưu.')
        if self.args.mode=='robot':
            end=time.monotonic()+2
            while time.monotonic()<end:rclpy.spin_once(self,timeout_sec=.1)
            existing=[name for name,ns in self.get_node_names_and_namespaces() if ns.rstrip('/')==self.get_namespace().rstrip('/') and name in ('slam_toolbox','amcl','bt_navigator','controller_server','social_safety')]
            if existing:raise RuntimeError('Đang có SLAM/Nav2/điều khiển cùng namespace. Dừng phiên cũ trước: '+', '.join(existing))
            topic=self.get_namespace().rstrip('/')+'/cmd_vel'
            if self.get_publishers_info_by_topic(topic):raise RuntimeError('Đang có nguồn xuất vận tốc khác; dừng bộ điều khiển cũ trước khi mở phiên mới.')
        if self.args.mode=='sim':
            self.start('world',['ros2','launch','tb4_cuoiky',self.args.scene+'_world_sim.launch.py','headless:=true'])
            if not self.args.no_gazebo_gui:self.start('gazebo_gui',['nice','-n','10','ign','gazebo','-g','-v','2'])
        else:self.component('robot_sensors','robot_sensors')
        self.mode_pub.publish(String(data='stop'))
        if self.args.catalog:
            catalog=LabCatalog(self.args.catalog);self.saved=catalog.path.parent
            self.component('nav','nav');self.phase='handover'
            meta=json.loads((self.saved/'map_metadata.json').read_text())
            pose=meta.get('spawn_initial_pose') if self.args.mode=='sim' else None
            self.publish('session_restoring','Đang mở lại map và các địa điểm đã lưu; không quét lại.')
            self.activate_saved(pose)
            return
        self.component('slam','slam');self.component('nav','nav');self.component('explorer','explorer')
        self.wait(lambda:self.map is not None and self.tf.can_transform('map','base_link',rclpy.time.Time()),120)
        bootstrap=self.runtime/'bootstrap';bootstrap.mkdir()
        command=['ros2','run','nav2_map_server','map_saver_cli','-f',str(bootstrap/'map'),'--ros-args','-r','__ns:=/'+self.args.namespace.strip('/'),'-p','use_sim_time:='+str(self.args.mode=='sim').lower()]
        result=subprocess.run(command,capture_output=True,text=True,timeout=30)
        if result.returncode:raise RuntimeError('Bootstrap map save failed: '+result.stderr[-600:])
        create_catalog(bootstrap/'map.yaml',bootstrap/'destinations.yaml')
        self.component('hri','hri',catalog=str(bootstrap/'destinations.yaml'),mapping_session='true')
        self.component('feedback','feedback')
        if not self.args.no_ui:
            self.component('ui','ui');self.start_rviz()
        self.phase='mapping';self.publish('session_mapping','Quét tự động hoặc điều khiển tay. Dừng quét, đặt tên map và xác nhận lưu để chuyển sang đặt địa điểm.')
        self.wait(lambda:self.control.get_subscription_count()>0,20)
        self.control.publish(String(data='auto' if self.args.auto else 'manual'))
        self.wait(lambda:self.saved is not None)
        self.control.publish(String(data='stop'))
        self.wait(lambda:self.mode=='stop' and self.stationary(),20)
        t=self.tf.lookup_transform('map','base_link',rclpy.time.Time()).transform
        pose=dict(x=t.translation.x,y=t.translation.y,yaw=yaw(t.rotation))
        self.phase='handover';self.publish('session_transition','Đã lưu map. Đang chuyển sang định vị để đặt địa điểm tùy ý.')
        self.stop('hri');self.stop('explorer');self.stop('slam')
        self.activate_saved(pose)

    def activate_saved(self,pose):
        self.tf.clear();self.amcl=None
        catalog=LabCatalog(self.saved/'destinations.yaml')
        self.component('localization','localization',catalog=str(catalog.path))
        if 'feedback' not in self.children:self.component('feedback','feedback')
        if not self.args.no_ui and 'ui' not in self.children:
            self.wait(lambda:self.map_matches(catalog),45)
            self.component('ui','ui');self.start_rviz()
        if pose is None:self.publish('waiting_initial_pose','Map đã mở. Chọn 2D Pose Estimate trong RViz để định vị robot thật tại vị trí hiện tại.')
        last=0
        end=time.monotonic()+90
        while rclpy.ok():
            rclpy.spin_once(self,timeout_sec=.05)
            if pose is not None and time.monotonic()-last>1:
                m=PoseWithCovarianceStamped();m.header.frame_id='map';m.header.stamp=self.get_clock().now().to_msg()
                m.pose.pose.position.x=pose['x'];m.pose.pose.position.y=pose['y'];m.pose.pose.orientation.z=math.sin(pose['yaw']/2);m.pose.pose.orientation.w=math.cos(pose['yaw']/2)
                m.pose.covariance[0]=m.pose.covariance[7]=m.pose.covariance[35]=.05;self.initial.publish(m);last=time.monotonic()
            if self.amcl and self.map_matches(catalog) and self.tf.can_transform('map','base_link',rclpy.time.Time()):break
            if pose is not None and time.monotonic()>end:raise TimeoutError('AMCL handover failed; robot stays stopped')
        if not rclpy.ok():raise KeyboardInterrupt
        self.mode_pub.publish(String(data='navigation'))
        self.hri_configuration=None
        self.component('hri','hri',catalog=str(catalog.path),mapping_session='false')
        self.wait(lambda:self.hri_configuration is not None and not self.hri_configuration['mapping_session'] and self.hri_configuration.get('ready_to_save',False),25)
        if not self.args.no_ui:
            self.stop('rviz');self.start_rviz()
        self.phase='navigation';self.report.update(catalog=str(catalog.path),handover_pose=pose)
        self.publish('session_ready','Map đã lưu và định vị sẵn sàng. Chọn Publish Point trên RViz hoặc đưa xe đến vị trí muốn đặt tên.')
        self.wait(lambda:False)

    def close(self):
        self.control.publish(String(data='stop'));self.mode_pub.publish(String(data='stop'))
        for key in list(self.children)[::-1]:self.stop(key)
        for f in self.files:f.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['sim','robot'],nargs='?',default='sim')
    parser.add_argument('--scene',choices=['maze','lab'],default='maze');parser.add_argument('--profile',default=str(ROOT/'config/profiles/robot.yaml'))
    parser.add_argument('--catalog',type=Path)
    parser.add_argument('--new-scan',action='store_true')
    parser.add_argument('--auto',action='store_true');parser.add_argument('--no-ui',action='store_true');parser.add_argument('--no-gazebo-gui',action='store_true')
    args=parser.parse_args();args.namespace=''
    if args.mode=='sim':
        if os.environ.get('ROS_DOMAIN_ID')!='98':raise RuntimeError('Simulation requires isolated domain 98')
        lock=Path('/tmp')/f'tb4_cuoiky_runtime_{os.getuid()}'
    else:
        cfg=yaml.safe_load(Path(args.profile).read_text())
        if cfg.get('mode')!='robot' or cfg.get('use_sim_time') or os.environ.get('ROS_DOMAIN_ID')=='98':raise RuntimeError('Use the real robot DDS environment and profile')
        args.namespace=cfg.get('namespace','').strip('/');lock=Path('/tmp')/f'tb4_robot_session_{os.getuid()}_{args.namespace}'
    ctx=storage.context(args.mode,args.scene,args.namespace)
    if args.new_scan and args.catalog:parser.error('--new-scan cannot be combined with --catalog')
    if not args.new_scan and args.catalog is None:args.catalog=storage.latest(ROOT,ctx)
    if args.catalog:
        c=LabCatalog(args.catalog);meta=json.loads((c.path.parent/'map_metadata.json').read_text())
        if meta.get('context',ctx)!=ctx:raise ValueError('Map belongs to a different simulation scene or robot; choose matching profile/scene.')
        if args.mode=='sim' and 'spawn_initial_pose' not in meta:raise ValueError('Saved map lacks simulation spawn alignment')
    lock.mkdir(exist_ok=True);pidfile=lock/'runner.pid'
    if pidfile.exists():
        try:os.kill(int(pidfile.read_text()),0)
        except ProcessLookupError:pass
        else:raise RuntimeError('A session is already running; stop it before starting another.')
    runtime=ROOT/'log/sessions'/time.strftime('%Y%m%d_%H%M%S');runtime.mkdir(parents=True)
    (ROOT/'results/latest_project_session.txt').write_text(str(runtime)+'\n')
    pidfile.write_text(str(os.getpid()))
    if args.mode=='sim':(lock/'current_partition').write_text(os.environ['IGN_PARTITION']+'\n')
    rclpy.init();node=Session(args,runtime)
    def quit_session(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,quit_session)
    try:node.run()
    except KeyboardInterrupt:pass
    except Exception as e:node.publish('session_failed',str(e));raise
    finally:
        node.close();node.destroy_node()
        if rclpy.ok():rclpy.shutdown()
        if pidfile.exists() and pidfile.read_text().strip()==str(os.getpid()):pidfile.unlink()

if __name__=='__main__':main()
