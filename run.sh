#!/usr/bin/env bash
# Build the image (first time only), build the ROS workspace and start Robopet.
# Usage: ./run.sh [launch args]      e.g.  ./run.sh speed:=20     ./run.sh gui:=false
#        ./run.sh stop               stop the container
set -euo pipefail
cd "$(dirname "$0")"
IMAGE=robopet-ros2
NAME=robopet

if [ "${1:-}" = stop ]; then docker stop "$NAME" >/dev/null 2>&1 || true; echo "stopped"; exit 0; fi

command -v docker >/dev/null || { echo "Docker is not installed." >&2; exit 1; }
curl -s -m 3 http://localhost:11434/api/tags >/dev/null \
  || echo "Warning: Ollama is not answering on localhost:11434. The pet will use its simple keyword fallback." >&2

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build -t "$IMAGE" docker
docker stop "$NAME" >/dev/null 2>&1 || true

xauth="${XAUTHORITY:-$HOME/.Xauthority}"; xa=()
[ -f "$xauth" ] && xa=(-e XAUTHORITY=/tmp/.xauth -v "$xauth":/tmp/.xauth:ro)
mkdir -p .home
docker run -d --rm --init --name "$NAME" --net=host --ipc=host \
  -u "$(id -u):$(id -g)" -e HOME=/home/me -v "$PWD/.home":/home/me \
  -e DISPLAY="${DISPLAY:-:0}" -v /tmp/.X11-unix:/tmp/.X11-unix:ro "${xa[@]}" \
  --device /dev/dri -v "$PWD":/ws "$IMAGE" sleep infinity >/dev/null
trap 'docker stop -t 1 "$NAME" >/dev/null 2>&1 || true' EXIT

tty=-i; [ -t 0 ] && tty=-it
docker exec $tty "$NAME" bash -c '
  source /opt/ros/jazzy/setup.bash
  export TURTLEBOT3_MODEL=burger
  cd /ws && colcon build --symlink-install --packages-select robopet 2>&1 | tail -3
  source install/setup.bash
  echo "Dashboard: http://localhost:8770   (Ctrl+C to stop)"
  ros2 launch robopet sim.launch.py '"$*"
