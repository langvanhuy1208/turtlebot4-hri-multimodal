"""Fresh maze simulation and the same confirmation controller used on hardware."""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetLaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution


def generate_launch_description():
    share = get_package_share_directory('tb4_cuoiky')
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='true'),
        DeclareLaunchArgument('start_rviz', default_value='true'),
        SetLaunchConfiguration('gesture_sensors', 'true'),
        SetLaunchConfiguration('sensor_render_engine', 'ogre2'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(
            PathJoinSubstitution([share, 'launch', 'sim_nav.launch.py'])),
            launch_arguments={'headless': LaunchConfiguration('headless'),
                              'start_rviz': LaunchConfiguration('start_rviz'),
                              'restamp_scans': 'false',
                              'map': PathJoinSubstitution([share, 'maps', 'bai7', 'map.yaml'])}.items()),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(
            PathJoinSubstitution([share, 'launch', 'lab_navigation.launch.py'])),
            launch_arguments={'catalog': PathJoinSubstitution([share, 'maps', 'demo', 'destinations.yaml']),
                              'use_sim_time': 'true', 'start_nav2': 'false', 'start_rviz': 'false',
                              }.items()),
    ])
