from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = [DeclareLaunchArgument(n, default_value=d) for n, d in [
        ('speed', '1.0'), ('pet_name', 'Bit'), ('llm_model', 'qwen2.5:7b'),
        ('llm_url', 'http://localhost:11434/api/chat')]]
    c = LaunchConfiguration
    return LaunchDescription(args + [
        Node(package='robopet', executable='needs', output='screen',
             parameters=[{'speed': c('speed')}]),
        Node(package='robopet', executable='brain', output='screen',
             parameters=[{'pet_name': c('pet_name'), 'llm_model': c('llm_model'), 'llm_url': c('llm_url')}]),
    ])
