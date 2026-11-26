# Robopet: a Tamagotchi robot pet (Proiect sincretic 1)

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

## Run (inside the `ros2` shell)
```bash
colcon build --symlink-install && source install/setup.bash   # once, and after code changes
robopet                  # Gazebo window + everything     (robopet gui:=false for no window; speed:=20 = 20x time)
```
Then open http://localhost:8770 or run `robopet-chat` in a second ROS window. Ollama must be running on the laptop (`systemctl status ollama`).

## Notes
- Memory file: `~/uni/ps1/ws/pet_memory.json` (delete it to make the pet forget you).
- Positions of the bowl, bed and toy are in `worlds/home.sdf` and `PLACES` in `motion.py`: change both together.
- Model: `llm_model:=qwen2.5:7b` (default). `qwen2.5:3b` was tested and is worse (wrong actions, drops the persona) and not much faster.
- Answers take about 6–15 s on this laptop (iGPU).
