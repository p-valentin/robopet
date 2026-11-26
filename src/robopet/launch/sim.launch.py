"""Robopet in Gazebo: the room, the robot, the body (needs), the mind (brain), the legs (motion), the web page.

  ros2 launch robopet sim.launch.py                 # Gazebo window + everything
  ros2 launch robopet sim.launch.py gui:=false      # no Gazebo window (lighter, for tests)
  ros2 launch robopet sim.launch.py speed:=20       # time runs 20x faster (needs drop quickly)
Then open http://localhost:8770 or run `ros2 run robopet chat`.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (AppendEnvironmentVariable, DeclareLaunchArgument, ExecuteProcess,
                            IncludeLaunchDescription, TimerAction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    tb3 = get_package_share_directory('turtlebot3_gazebo')
    ros_gz = get_package_share_directory('ros_gz_sim')
    world = os.path.join(get_package_share_directory('robopet'), 'worlds', 'home.sdf')
    c = LaunchConfiguration

    args = [DeclareLaunchArgument(n, default_value=d) for n, d in [
        ('gui', 'true'), ('speed', '1.0'), ('pet_name', 'Bit'), ('llm_model', 'qwen2.5:7b'),
        ('llm_url', 'http://localhost:11434/api/chat')]]

    def include(path, **kw):
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(path), launch_arguments=kw.items())

    return LaunchDescription(args + [
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(tb3, 'models')),
        include(os.path.join(ros_gz, 'launch', 'gz_sim.launch.py'),
                gz_args=f'-r -s -v2 {world}', on_exit_shutdown='true'),
        IncludeLaunchDescription(  # the Gazebo window
            PythonLaunchDescriptionSource(os.path.join(ros_gz, 'launch', 'gz_sim.launch.py')),
            launch_arguments={'gz_args': '-g -v2 ', 'on_exit_shutdown': 'true'}.items(),
            condition=IfCondition(c('gui'))),
        # Gazebo opens with a low camera that shows only a corner: look straight down at the room.
        TimerAction(period=8.0, condition=IfCondition(c('gui')), actions=[ExecuteProcess(cmd=[
            'gz', 'service', '-s', '/gui/move_to/pose', '--reqtype', 'gz.msgs.GUICamera',
            '--reptype', 'gz.msgs.Boolean', '--timeout', '3000', '--req',
            'pose: {position: {x: 0, y: 0, z: 4.5}, orientation: {x: -0.5, y: 0.5, z: 0.5, w: 0.5}}'])]),
        include(os.path.join(tb3, 'launch', 'robot_state_publisher.launch.py'), use_sim_time='true'),
        include(os.path.join(tb3, 'launch', 'spawn_turtlebot3.launch.py'), x_pose='0.0', y_pose='0.0'),
        Node(package='robopet', executable='needs', output='screen', parameters=[{'speed': c('speed')}]),
        Node(package='robopet', executable='brain', output='screen',
             parameters=[{'pet_name': c('pet_name'), 'llm_model': c('llm_model'), 'llm_url': c('llm_url')}]),
        Node(package='robopet', executable='motion', output='screen'),
        Node(package='robopet', executable='dashboard', output='screen'),
    ])
