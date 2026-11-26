# ROS 2 Jazzy (Ubuntu 24.04) + Gazebo Harmonic + TurtleBot3, everything Robopet needs.
FROM osrf/ros:jazzy-desktop-full
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-turtlebot3 ros-jazzy-turtlebot3-msgs ros-jazzy-turtlebot3-simulations \
      python3-colcon-common-extensions git nano \
    && rm -rf /var/lib/apt/lists/*
RUN echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc \
 && echo 'export TURTLEBOT3_MODEL=burger' >> /root/.bashrc \
 && echo '[ -f /ws/install/setup.bash ] && source /ws/install/setup.bash' >> /root/.bashrc
WORKDIR /ws
