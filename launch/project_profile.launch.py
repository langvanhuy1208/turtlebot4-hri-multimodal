"""Launch saved-map HRI with one explicit deployment profile."""
from pathlib import Path
import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,OpaqueFunction,GroupAction,IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node,PushRosNamespace,SetRemap
from ament_index_python.packages import get_package_share_directory


def setup(context):
    share=Path(get_package_share_directory('tb4_cuoiky'))
    profile=yaml.safe_load(Path(LaunchConfiguration('profile').perform(context)).read_text())
    catalog=Path(LaunchConfiguration('catalog').perform(context)).resolve()
    data=yaml.safe_load(catalog.read_text());mapfile=str((catalog.parent/data['map']).resolve())
    mode=profile['mode'];ns=profile.get('namespace','').strip('/')
    if mode not in ('simulation','robot'):raise ValueError('Unknown profile mode')
    clock=bool(profile['use_sim_time'])
    if mode=='robot' and (clock or profile.get('perception')!='rgb_yolo_lidar'):raise ValueError('Robot requires real clock and real perception')
    nav=Path(get_package_share_directory('turtlebot4_navigation'))
    actions=[]
    # Existing HRI interfaces are explicitly remapped as a group, including absolute legacy names.
    names=['robot_description','plan','local_plan','local_costmap/costmap','global_costmap/costmap','goal_pose','clicked_point','hri/catalog','hri/selected_point','session/control','hri/voice','hri/status','hri/decision','hri/safety','hri/speech_active','hri/camera_enabled','hri/microphone_enabled','hri/listening_state','detected_gesture','semantic_regions','voice_nav/route','voice_nav/transcript','perception/people','mapping/control','mapping/mode','map','odom','initialpose','amcl_pose','cmd_vel','cmd_vel_requested','cmd_vel_manual','scan','scan_nav','tf','tf_static','joy','hmi/buttons']
    if ns:actions.extend(SetRemap('/'+name,'/'+ns+'/'+name) for name in names)
    actions.append(PushRosNamespace(ns))
    # Nav2's launch applies the namespace as the parameter root; avoid double PushRosNamespace.
    actions.extend([
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(Path(get_package_share_directory('nav2_bringup'))/'launch/localization_launch.py')),
            launch_arguments=dict(map=mapfile,params_file=str(share/'config/localization.yaml'),use_sim_time=str(clock).lower(),namespace=ns,use_composition='False').items()),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share/'launch/guarded_navigation.launch.py')),
            launch_arguments=dict(params_file=str(share/'config/nav2.yaml'),use_sim_time=str(clock).lower(),namespace=ns).items()),
        Node(package='tb4_cuoiky',executable='lab_hri_node.py',parameters=[dict(regions_file=str(catalog),use_sim_time=clock)],
             remappings=[('/voice_command','/'+ns+'/hri/voice' if ns else '/hri/voice'),('/voice_nav/status','/'+ns+'/hri/status' if ns else '/hri/status')]),
        Node(package='tb4_cuoiky',executable='feedback_node.py'),
    ])
    if mode=='robot':
        actions.extend([
            Node(package='tb4_cuoiky',executable='scan_retimestamp.py',parameters=[dict(restamp=False,use_sim_time=False)]),
            Node(package='tb4_cuoiky',executable='person_perception.py',parameters=[dict(model=str(share/'models/yolov8n.pt'),rgb_topic=profile['rgb_topic'],info_topic=profile['info_topic'])]),
            Node(package='tb4_cuoiky',executable='safety_node.py',parameters=[{k:profile[k] for k in ['warning_distance','stop_distance','clear_hold']}]),
        ])
    project=Path(__file__).resolve().parents[1]
    actions.extend([
        Node(package='tb4_cuoiky',executable='hri_panel.py',condition=IfCondition(LaunchConfiguration('start_ui'))),
        Node(executable=str(project/'.venv-gesture/bin/python'),arguments=[str(project/'scripts/gesture_recognition_node.py')],
             parameters=[dict(model_path=str(share/'models/gesture_recognizer.task'),camera_index=0,hri_mode=True)],condition=IfCondition(LaunchConfiguration('start_ui'))),
        Node(package='rviz2',executable='rviz2',arguments=['-d',str(share/'config/nav_voice.rviz')],parameters=[dict(use_sim_time=clock)],condition=IfCondition(LaunchConfiguration('start_ui'))),
    ])
    return [GroupAction(actions)]


def generate_launch_description():
    share=Path(get_package_share_directory('tb4_cuoiky'))
    return LaunchDescription([DeclareLaunchArgument('profile',default_value=str(share/'config/profiles/robot.yaml')),
                              DeclareLaunchArgument('catalog'),DeclareLaunchArgument('start_ui',default_value='true'),OpaqueFunction(function=setup)])
