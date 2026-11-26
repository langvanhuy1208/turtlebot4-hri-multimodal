"""Sensor-only lab world: SLAM and navigation are started separately."""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetLaunchConfiguration, TimerAction, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('tb4_cuoiky')
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='true'),
        SetLaunchConfiguration('gesture_sensors', 'true'),
        SetLaunchConfiguration('sensor_render_engine', 'ogre2'),
        SetLaunchConfiguration('world_file', PathJoinSubstitution([share, 'worlds', 'maze_hri.sdf'])),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(
            PathJoinSubstitution([share, 'launch', 'turtlebot4_ignition_fast.launch.py'])),
            launch_arguments={'world': 'maze', 'headless': LaunchConfiguration('headless'), 'rviz': 'false',
                              'x': '2.0', 'y': '0.0', 'z': '0.01', 'yaw': '3.141592653589793'}.items()),
        Node(package='tb4_cuoiky', executable='odom_tf_broadcaster.py',
             parameters=[{'use_sim_time': True}], output='screen'),
        Node(package='tb4_cuoiky', executable='scan_retimestamp.py',
             parameters=[{'use_sim_time': True, 'restamp': False}], output='screen'),
        Node(package='tb4_cuoiky', executable='safety_node.py', parameters=[{'use_sim_time':True}], output='screen'),
        Node(package='tb4_cuoiky', executable='sim_people.py', output='screen'),
        Node(package='ros_gz_bridge', executable='parameter_bridge',
             arguments=['/world/maze/pose/info@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V'],
             remappings=[('/world/maze/pose/info', '/simulation/model_poses')],output='screen'),
        TimerAction(period=20.0, actions=[ExecuteProcess(cmd=[
            'ign','service','-s','/world/maze/remove','--reqtype','ignition.msgs.Entity',
            '--reptype','ignition.msgs.Boolean','--timeout','3000','--req',
            'name: "standard_dock" type: MODEL'], output='screen')]),
    ])
