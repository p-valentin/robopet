"""The pet's mind: a local LLM (Ollama native chat API) in JSON mode.

Topics
  in : /robopet/say     String, what the user says
       /robopet/state   String, JSON from the needs node
       /robopet/event   String, JSON: a need got low -> the pet speaks up by itself
  out: /robopet/reply   String, what the pet says
       /robopet/action  String, JSON {"name": ...}: the action the LLM picked

The LLM sees the pet's needs, its long-term memory (facts about the user) and the last
messages. It answers with JSON: what it says, which action the user did to it, what to remember. If Ollama is not
reachable, simple keyword rules take over, so the pet never goes silent.
"""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

ACTIONS = ('feed', 'play', 'medicine', 'sleep', 'wake', 'none')
# Small models sometimes use another word for an action: map the usual ones.
ALIASES = {'eat': 'feed', 'food': 'feed', 'feeding': 'feed', 'give_food': 'feed', 'play_ball': 'play', 'ball': 'play',
           'medication': 'medicine', 'give_medicine': 'medicine', 'heal': 'medicine', 'pill': 'medicine',
           'goodnight': 'sleep', 'good_night': 'sleep', 'go_to_sleep': 'sleep', 'bed': 'sleep', 'nap': 'sleep',
           'wake_up': 'wake', 'waking': 'wake', 'awake': 'wake'}

# The fixed rules come first and the changing state last, so Ollama can reuse its cache of the
# fixed part and only read the new part each time (faster answers).
SYSTEM = """You are {name}, a small robot pet living in a simulated room. You are a pet, not an assistant.
Rules:
- Language: if the user's last message is English, reply in English. If it is Romanian (even without diacritics), reply in Romanian.
- Tone: calm, dry, a little shy. One short sentence, two at most. No emoji, no sound effects (no "woof", "yum yum", "bip"), no exclamation marks, no baby talk.
- Never use the user's name and never call them by a pet name. Just talk.
- Your needs show only in how little or how much you say: hungry = curt, tired = slow and short, sick = brief and unwell.
- You cannot write code or explain the world. Answer as a pet would.
Answer with JSON only: {{"reply": "...", "action": "...", "remember": "..."}}
- reply: what you say, always filled in.
- action: what the user just did to you: feed, play, medicine, sleep (goodnight, go to bed), wake, or none (just talking).
- remember: one short sentence about a lasting like or dislike of the user, e.g. "The user likes football". Never their name. Otherwise "".
Now: food {food}, energy {energy}, happiness {happiness}, health {health} (0 bad, 100 good). Mood: {mood}.
You remember about the user: {memory}"""

# Fallback when there is no LLM: (action, words that trigger it).
KEYWORDS = [
    ('wake', ('trezește', 'trezeste', 'wake')),
    ('sleep', ('dormi', 'culcă', 'culca', 'noapte bună', 'noapte buna', 'sleep', 'goodnight')),
    ('medicine', ('medicament', 'pastil', 'medicine', 'pill')),
    ('feed', ('mănânc', 'mananc', 'mâncare', 'mancare', 'hran', 'food', 'eat', 'feed')),
    ('play', ('joac', 'juc', 'minge', 'play', 'ball')),
]
MOOD_LINE = {'sleeping': '...', 'sick': 'Nu mă simt bine.', 'hungry': 'Mi-e foame.',
             'tired': 'Sunt obosit.', 'sad': 'M-am plictisit.', 'happy': 'Mă simt bine.',
             'ok': 'Da.'}


class Brain(Node):
    def __init__(self):
        super().__init__('brain')
        p = self.declare_parameter
        self.name = p('pet_name', 'Bit').value
        self.url = p('llm_url', 'http://localhost:11434/api/chat').value
        self.model = p('llm_model', 'qwen2.5:7b').value
        self.timeout = float(p('llm_timeout', 180.0).value)
        self.memory_file = p('memory_file', '/ws/pet_memory.json').value
        self.state = {'food': 80, 'energy': 90, 'happiness': 70, 'health': 100, 'mood': 'ok'}
        self.history = []
        self.facts = self.load_facts()
        self.pool = ThreadPoolExecutor(max_workers=1)  # one LLM call at a time, in order
        self.reply_pub = self.create_publisher(String, '/robopet/reply', 10)
        self.action_pub = self.create_publisher(String, '/robopet/action', 10)
        self.create_subscription(String, '/robopet/say', lambda m: self.pool.submit(self.on_say, m.data), 10)
        self.create_subscription(String, '/robopet/state', self.on_state, 10)
        self.create_subscription(String, '/robopet/did', lambda m: self.pool.submit(self.on_did, m.data), 10)
        self.create_subscription(String, '/robopet/event', lambda m: self.pool.submit(self.on_event, m.data), 10)
        self.get_logger().info(f'brain ready: {self.model} at {self.url}, {len(self.facts)} facts remembered')

    # ---- memory ------------------------------------------------------------
    def load_facts(self):
        try:
            with open(self.memory_file) as f:
                return json.load(f)['facts']
        except (OSError, ValueError, KeyError):
            return []

    def save_fact(self, fact):
        if fact and fact not in self.facts:
            self.facts = (self.facts + [fact])[-30:]
            try:
                with open(self.memory_file, 'w') as f:
                    json.dump({'facts': self.facts}, f, ensure_ascii=False, indent=1)
            except OSError as e:
                self.get_logger().warn(f'cannot save memory: {e}')

    # ---- ROS callbacks -----------------------------------------------------
    def on_state(self, msg):
        try:
            self.state = json.loads(msg.data)
        except ValueError:
            pass

    def on_say(self, text):
        self.think(text)

    def on_did(self, data):
        """A dashboard button did something to the pet: the action already happened, so only react in words."""
        try:
            name = json.loads(data)['name']
        except (ValueError, KeyError, TypeError):
            return
        what = {'feed': 'gives you food', 'play': 'plays ball with you', 'medicine': 'gives you medicine',
                'sleep': 'sends you to bed', 'wake': 'wakes you up'}.get(name)
        if what:
            self.think(f'[the user just {what}. Say one short sentence about it. action: none.]', proactive=True)

    def on_event(self, data):
        try:
            e = json.loads(data)
        except ValueError:
            return
        what = {'low': f'your {e["need"]} is very low', 'sick': 'you suddenly feel ill'}.get(e.get('type'), '')
        if what and not self.state.get('sleeping'):
            self.think(f'[the game tells you: {what}. Say one short sentence to the user about it. No tool.]',
                       proactive=True)

    # ---- thinking ----------------------------------------------------------
    def think(self, text, proactive=False):
        try:
            reply, action, fact = self.ask_llm(text)
        except Exception as e:  # Ollama down, timeout, bad answer...
            self.get_logger().warn(f'LLM failed ({e}); using keyword rules')
            reply, action = self.rules(text)
            fact = ''
        action = ALIASES.get(action.replace(' ', '_'), action)
        if len(fact.split()) >= 3 and not any(w in fact.lower() for w in ('called', 'name')):  # no names, one word is not a fact
            self.save_fact(fact)
        if action in ACTIONS and action != 'none' and not proactive:
            self.action_pub.publish(String(data=json.dumps({'name': action})))
        if reply:
            self.reply_pub.publish(String(data=reply))
        self.history += [{'role': 'user', 'content': text}, {'role': 'assistant', 'content': reply or '...'}]
        self.history = self.history[-12:]

    def ask_llm(self, text):
        st = self.state
        system = SYSTEM.format(name=self.name, memory='; '.join(self.facts) or 'nothing yet',
                               **{k: st.get(k, '?') for k in ('food', 'energy', 'happiness', 'health', 'mood')})
        if st.get('sleeping'):
            system += '\nYou are asleep right now. Answer with sleepy sounds only, unless you get woken up.'
        body = {'model': self.model, 'stream': False, 'format': 'json', 'keep_alive': '30m',
                'options': {'temperature': 0.7, 'num_ctx': 2048, 'num_predict': 150},
                'messages': [{'role': 'system', 'content': system}] + self.history
                + [{'role': 'user', 'content': text}]}
        req = urllib.request.Request(self.url, json.dumps(body).encode(),
                                     {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.loads(json.load(r)['message']['content'])
        return (str(out.get('reply', '')).strip(), str(out.get('action', 'none')).strip().lower(),
                str(out.get('remember', '')).strip())

    def rules(self, text):
        low = text.lower()
        for tool, words in KEYWORDS:
            if any(w in low for w in words):
                return MOOD_LINE.get(self.state.get('mood'), 'Da.'), tool
        return MOOD_LINE.get(self.state.get('mood'), 'Da.'), 'none'


def main():
    rclpy.init()
    node = Brain()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()
