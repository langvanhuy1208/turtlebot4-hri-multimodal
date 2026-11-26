"""Real lab map + stock TurtleBot 4 navigation parameters + confirmed HRI."""
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def setup(context):
    nav = get_package_share_directory('turtlebot4_navigation')
    share = get_package_share_directory('tb4_cuoiky')
    catalog = Path(LaunchConfiguration('catalog').perform(context)).expanduser().resolve()
    data = yaml.safe_load(catalog.read_text())
    map_file = str((catalog.parent / data['map']).resolve())
    clock = LaunchConfiguration('use_sim_time')
    actions = []
    for filename, args in [
            ('localization.launch.py', {'map': map_file, 'params': LaunchConfiguration('localization_params')}),
            ('guarded_navigation.launch.py', {'params_file': LaunchConfiguration('nav_params')})]:
        actions.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(
            PathJoinSubstitution([share if filename=='guarded_navigation.launch.py' else nav, 'launch', filename])),
            launch_arguments={'use_sim_time': clock, **args}.items(),
            condition=IfCondition(LaunchConfiguration('start_nav2'))))
    actions.extend([
        Node(package='tb4_cuoiky', executable='feedback_node.py', output='screen'),
        Node(package='tb4_cuoiky', executable='lab_hri_node.py', output='screen',
             parameters=[{'regions_file': str(catalog),
                          'use_sim_time': ParameterValue(clock, value_type=bool),
                          'enable_hmi_buttons': ParameterValue(LaunchConfiguration('hmi_buttons'), value_type=bool),
                          'enable_joy_buttons': ParameterValue(LaunchConfiguration('joy_buttons'), value_type=bool),
                          'confirm_button': ParameterValue(LaunchConfiguration('confirm_button'), value_type=int),
                          'cancel_button': ParameterValue(LaunchConfiguration('cancel_button'), value_type=int)}],
             remappings=[('/voice_command', '/hri/voice'), ('/voice_nav/status', '/hri/status')]),
        Node(package='rviz2', executable='rviz2',
             arguments=['-d', PathJoinSubstitution([share, 'config', 'nav_voice.rviz'])],
             parameters=[{'use_sim_time': ParameterValue(clock, value_type=bool)}],
             condition=IfCondition(LaunchConfiguration('start_rviz'))),
    ])
    return actions


def generate_launch_description():
    nav = get_package_share_directory('turtlebot4_navigation')
    return LaunchDescription([
        DeclareLaunchArgument('catalog', description='Absolute path to lab destinations YAML'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('start_nav2', default_value='true'),
        DeclareLaunchArgument('start_rviz', default_value='true'),
        DeclareLaunchArgument('hmi_buttons', default_value='false'),
        DeclareLaunchArgument('joy_buttons', default_value='false'),
        DeclareLaunchArgument('confirm_button', default_value='0'),
        DeclareLaunchArgument('cancel_button', default_value='1'),
        DeclareLaunchArgument('nav_params', default_value=PathJoinSubstitution([nav, 'config', 'nav2.yaml'])),
        DeclareLaunchArgument('localization_params', default_value=PathJoinSubstitution([nav, 'config', 'localization.yaml'])),
        OpaqueFunction(function=setup),
    ])
