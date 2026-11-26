from glob import glob
from setuptools import setup

package_name = 'robopet'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/worlds', glob('worlds/*.sdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='p-valentin',
    maintainer_email='p-valentin@users.noreply.github.com',
    description='Robot pet with 4 needs and a local LLM brain.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'needs = robopet.needs:main',
            'brain = robopet.brain:main',
            'chat = robopet.chat:main',
            'motion = robopet.motion:main',
            'dashboard = robopet.dashboard:main',
        ],
    },
)
