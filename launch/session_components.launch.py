"""Shared session components for simulation and connected Humble robots."""
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,GroupAction,IncludeLaunchDescription,OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node,PushRosNamespace,SetRemap


def setup(context):
    def arg(k):return LaunchConfiguration(k).perform(context)
    share=Path(get_package_share_directory('tb4_cuoiky'));root=Path(__file__).resolve().parents[1]
    ns=arg('namespace').strip('/');clock=arg('use_sim_time')=='true';role=arg('component')
    params=dict(use_sim_time=clock)
    names=['robot_description','plan','local_plan','local_costmap/costmap','global_costmap/costmap','goal_pose','clicked_point','hri/catalog','hri/selected_point','hri/voice','hri/status','hri/decision','hri/safety','hri/speech_active','hri/camera_enabled','hri/microphone_enabled','hri/listening_state','session/control','detected_gesture','semantic_regions','voice_nav/route','voice_nav/transcript','perception/people','mapping/control','mapping/status','mapping/mode','map','odom','initialpose','amcl_pose','cmd_vel','cmd_vel_requested','cmd_vel_manual','scan','scan_nav','tf','tf_static','joy','hmi/buttons']
    actions=[SetRemap('/'+name,'/'+ns+'/'+name) for name in names] if ns else []
    actions.append(PushRosNamespace(ns))
    def include(package,file,**kwargs):
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(Path(get_package_share_directory(package))/'launch'/file)),launch_arguments=kwargs.items())
    if role=='slam':
        return [include('turtlebot4_navigation','slam.launch.py',namespace=ns,use_sim_time=arg('use_sim_time'),sync='false',params=str(share/'config/slam.yaml'))]
    if role=='nav':
        actions.append(include('tb4_cuoiky','guarded_navigation.launch.py',namespace=ns,use_sim_time=arg('use_sim_time'),params_file=str(share/'config/nav2.yaml')))
    elif role=='localization':
        catalog=Path(arg('catalog'));data=yaml.safe_load(catalog.read_text())
        actions.append(include('nav2_bringup','localization_launch.py',namespace=ns,use_sim_time=arg('use_sim_time'),use_composition='False',map=str((catalog.parent/data['map']).resolve()),params_file=str(share/'config/localization.yaml')))
    elif role=='hri':
        actions.append(Node(package='tb4_cuoiky',executable='lab_hri_node.py',parameters=[dict(**params,regions_file=arg('catalog'),mapping_session=arg('mapping_session')=='true')],remappings=[('/voice_command','/'+ns+'/hri/voice' if ns else '/hri/voice'),('/voice_nav/status','/'+ns+'/hri/status' if ns else '/hri/status')]))
    elif role=='explorer':
        actions.append(Node(package='tb4_cuoiky',executable='frontier_explorer.py',parameters=[params]))
    elif role=='ui':
        actions.extend([
            Node(package='tb4_cuoiky',executable='hri_panel.py'),
            Node(executable=str(root/'.venv-gesture/bin/python'),arguments=[str(root/'scripts/gesture_recognition_node.py')],parameters=[dict(model_path=str(share/'models/gesture_recognizer.task'),camera_index=0,hri_mode=True)]),
        ])
    elif role=='rviz':
        config=arg('rviz_config') or str(share/'config'/('nav_maze.rviz' if arg('scene')=='maze' else 'nav_voice.rviz'))
        actions.append(Node(package='rviz2',executable='rviz2',arguments=['-d',config],parameters=[params]))
    elif role=='feedback':actions.append(Node(package='tb4_cuoiky',executable='feedback_node.py'))
    elif role=='robot_sensors':
        cfg=yaml.safe_load(Path(arg('profile')).read_text())
        actions.extend([
            Node(package='tb4_cuoiky',executable='scan_retimestamp.py',parameters=[dict(restamp=False,use_sim_time=False)]),
            Node(package='tb4_cuoiky',executable='person_perception.py',parameters=[dict(model=str(share/'models/yolov8n.pt'),rgb_topic=cfg['rgb_topic'],info_topic=cfg['info_topic'])]),
            Node(package='tb4_cuoiky',executable='safety_node.py',parameters=[{k:cfg[k] for k in ['warning_distance','stop_distance','clear_hold']}]),
        ])
    else:raise ValueError('Unknown session component '+role)
    return [GroupAction(actions)]


def generate_launch_description():
    defaults=dict(component='hri',namespace='',use_sim_time='true',catalog='',mapping_session='false',scene='maze',profile='',rviz_config='')
    return LaunchDescription([*[DeclareLaunchArgument(k,default_value=v) for k,v in defaults.items()],OpaqueFunction(function=setup)])
