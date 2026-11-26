"""The pet's body: four needs that change over time, and the actions that change them.

Topics
  in : /robopet/action         String, JSON {"name": "feed"}   (feed, play, medicine, sleep, wake)
  out: /robopet/state          String, JSON, once per second
       /robopet/action_result  String, JSON {"name", "ok", "note"}
       /robopet/event          String, JSON {"type": "low", "need": "food"} when a need gets low
Parameter `speed` makes simulated time faster (speed:=20 for demos).
"""
import json
import random

import rclpy
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from std_msgs.msg import String

NEEDS = ('food', 'energy', 'happiness', 'health')
LOW = 25      # a need below this is "low": the pet complains once
RECOVER = 40  # it must go above this before it can complain again
MIN_NAP = 40  # simulated seconds: long enough to walk to the bed and really sleep there


def clamp(x):
    return max(0.0, min(100.0, x))


class Needs(Node):
    def __init__(self):
        super().__init__('needs')
        # dynamic typing: launch files pass text, the command line passes numbers; float() accepts both
        self.speed = float(self.declare_parameter(
            'speed', 1.0, ParameterDescriptor(dynamic_typing=True)).value)
        self.v = {'food': 80.0, 'energy': 90.0, 'happiness': 70.0, 'health': 100.0}
        self.sleeping = False
        self.slept = 0.0  # simulated seconds asleep in this nap
        self.complained = set()
        self.state_pub = self.create_publisher(String, '/robopet/state', 10)
        self.result_pub = self.create_publisher(String, '/robopet/action_result', 10)
        self.event_pub = self.create_publisher(String, '/robopet/event', 10)
        self.create_subscription(String, '/robopet/action', self.on_action, 10)
        self.dt = 1.0
        self.create_timer(self.dt, self.tick)
        self.get_logger().info(f'needs ready (speed x{self.speed})')

    # ---- time passes -------------------------------------------------------
    def tick(self):
        s = self.dt * self.speed
        v = self.v
        if self.sleeping:
            self.slept += s
            v['energy'] = clamp(v['energy'] + 0.5 * s)
            v['food'] = clamp(v['food'] - 0.04 * s)
            if v['energy'] >= 100 and self.slept >= MIN_NAP:  # a nap lasts at least MIN_NAP seconds
                self.sleeping = False
        else:
            v['food'] = clamp(v['food'] - 0.06 * s)
            v['energy'] = clamp(v['energy'] - 0.03 * s)
            v['happiness'] = clamp(v['happiness'] - 0.04 * s)
            if v['energy'] < 10:  # exhausted: falls asleep by itself
                self.sleeping, self.slept = True, 0.0
        # health: starves or tires out -> drops; looked after -> slowly heals
        if v['food'] < 15 or v['energy'] < 8:
            v['health'] = clamp(v['health'] - 0.25 * s)
        elif v['food'] > 50:
            v['health'] = clamp(v['health'] + 0.02 * s)
        if random.random() < 0.002 * s:  # random sickness
            v['health'] = clamp(v['health'] - 15)
            self.event('sick', 'health')
        self.check_low()
        self.publish_state()

    def check_low(self):
        for n in NEEDS:
            if self.v[n] < LOW and n not in self.complained:
                self.complained.add(n)
                self.event('low', n)
            elif self.v[n] > RECOVER:
                self.complained.discard(n)

    def event(self, kind, need):
        self.event_pub.publish(String(data=json.dumps({'type': kind, 'need': need})))

    # ---- actions -----------------------------------------------------------
    def on_action(self, msg):
        try:
            name = json.loads(msg.data)['name']
        except (ValueError, KeyError, TypeError):
            return
        ok, note = self.apply(name)
        self.result_pub.publish(String(data=json.dumps({'name': name, 'ok': ok, 'note': note})))
        self.publish_state()

    def apply(self, name):
        v = self.v
        if self.sleeping and name != 'wake':
            return False, 'sleeping: only "wake" works'
        if name == 'feed':
            if v['food'] > 95:
                return False, 'not hungry'
            v['food'] = clamp(v['food'] + 35)
            v['happiness'] = clamp(v['happiness'] + 3)
        elif name == 'play':
            if v['energy'] < 15:
                return False, 'too tired to play'
            v['happiness'] = clamp(v['happiness'] + 25)
            v['energy'] = clamp(v['energy'] - 10)
            v['food'] = clamp(v['food'] - 8)
        elif name == 'medicine':
            v['health'] = clamp(v['health'] + 30)
            v['happiness'] = clamp(v['happiness'] - 5)
        elif name == 'sleep':
            self.sleeping = True
            self.slept = 0.0
        elif name == 'wake':
            if not self.sleeping:
                return False, 'already awake'
            self.sleeping = False
            if v['energy'] < 40:
                v['happiness'] = clamp(v['happiness'] - 8)
                return True, 'woken up too early: grumpy'
        else:
            return False, f'unknown action {name}'
        return True, 'done'

    # ---- state -------------------------------------------------------------
    def mood(self):
        v = self.v
        if self.sleeping:
            return 'sleeping'
        if v['health'] < 35:
            return 'sick'
        if v['food'] < LOW:
            return 'hungry'
        if v['energy'] < LOW:
            return 'tired'
        if v['happiness'] < 30:
            return 'sad'
        if min(v.values()) > 60:
            return 'happy'
        return 'ok'

    def publish_state(self):
        d = {k: round(x) for k, x in self.v.items()}
        d.update(sleeping=self.sleeping, mood=self.mood())
        self.state_pub.publish(String(data=json.dumps(d)))


def main():
    rclpy.init()
    node = Needs()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()
