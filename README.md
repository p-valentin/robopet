# Robopet

A TurtleBot3 in a small Gazebo room is a pet with four needs. A **local LLM** (Ollama, `qwen2.5:7b`) is its brain:
you talk to it, it answers in character, decides what you did to it (feed, play, medicine, sleep, wake) and remembers
facts about you. It walks to its bowl, its bed and its toy by itself.

```
dashboard / chat ──/robopet/say──► brain ──/robopet/action──► needs ──/robopet/state──► brain, motion, dashboard
   ▲                                │                           │
   └──────── /robopet/reply ◄───────┘          motion ──/cmd_vel──► TurtleBot3 (Gazebo)
```
| Node | Job |
|---|---|
| `needs` | food, energy, happiness, health; decay over time; applies actions; raises "need is low" events |
| `brain` | prompt = rules + needs + memory + last messages → Ollama (JSON mode) → reply, action, fact. Keyword fallback if Ollama is down |
| `motion` | go to bowl / bed / toy, wiggle, spin; chooses by itself when idle (sleepy → bed, hungry → bowl, else wander) |
| `dashboard` | web page http://localhost:8770: face, need bars, chat, quick buttons |
| `chat` | terminal chat, `/status` |

## Quick start (Linux, Docker + Ollama)
Everything runs in Docker (ROS 2 Jazzy, Gazebo Harmonic, TurtleBot3), so you do not need Ubuntu 24.04 or ROS on your machine.

```bash
# 1. a local LLM (https://ollama.com)
ollama pull qwen2.5:7b

# 2. run it (the first run builds the Docker image, about 5-10 min)
git clone https://github.com/p-valentin/robopet.git && cd robopet
./run.sh                 # Gazebo window + pet. Options: ./run.sh speed:=20   ./run.sh gui:=false
```
Then open **http://localhost:8770**: talk to the pet or press Feed / Play / Sleep and watch the robot walk to its bowl, bed or toy.
Stop with Ctrl+C or `./run.sh stop`.

Needs: Docker, Ollama running on the host (port 11434), an X11/XWayland desktop for the Gazebo window (use `gui:=false` without one).
Without Ollama the pet still works with a simple keyword fallback.

## Notes
- Memory file: `pet_memory.json` in the repo folder (delete it to make the pet forget you).
- Positions of the bowl, bed and toy are in `src/robopet/worlds/home.sdf` and `PLACES` in `motion.py`: change both together.
- Model: `./run.sh llm_model:=qwen2.5:3b` to try another one. `qwen2.5:7b` is the default; 3B was tested and is worse (wrong actions, drops the persona).
- Answers take about 6-15 s on a laptop iGPU.
- The robot's speed, the needs decay and the Gazebo room are plain parameters and files: fork and change them.

License: MIT
