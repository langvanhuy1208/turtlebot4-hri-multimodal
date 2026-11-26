"""Real TurtleBot 4 SLAM; existing robot bringup supplies scan/odom/TF."""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    nav = get_package_share_directory('turtlebot4_navigation')
    share = get_package_share_directory('tb4_cuoiky')
    clock = LaunchConfiguration('use_sim_time')
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('start_rviz', default_value='true'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(
            PathJoinSubstitution([nav, 'launch', 'slam.launch.py'])),
            launch_arguments={'use_sim_time': clock, 'sync': 'false'}.items()),
        Node(package='rviz2', executable='rviz2',
             arguments=['-d', PathJoinSubstitution([share, 'config', 'nav.rviz'])],
             parameters=[{'use_sim_time': ParameterValue(clock, value_type=bool)}],
             condition=IfCondition(LaunchConfiguration('start_rviz'))),
    ])
