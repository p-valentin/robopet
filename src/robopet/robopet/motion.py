"""The pet's legs: drives the TurtleBot3 in Gazebo to the bowl, the bed and the toy.

Topics
  in : /robopet/action  String JSON {"name": ...}   what the user did (from the brain)
       /robopet/state   String JSON                 needs and mood (from the needs node)
       /odom            nav_msgs/Odometry           where the robot is
  out: /cmd_vel         geometry_msgs/TwistStamped  wheel commands
       /robopet/activity String                     what the pet is doing, in words

Each action becomes a short list of steps ("go to the bowl", "wiggle for 3 s"). When it has
nothing to do, the pet decides by itself: sleepy -> bed, hungry -> bowl, bored -> wander.
"""
import json
import math
import random

import rclpy
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

# Where to stand (x, y in metres, same frame as the Gazebo world: robot spawns at 0, 0).
# Next to the bowl and the toy, on the bed: they match worlds/home.sdf (the objects have no collision).
PLACES = {'bowl': (2.0, 1.6), 'bed': (-2.4, 1.6), 'toy': (1.55, -2.0), 'home': (0.0, 0.0)}
MAX_LIN, MAX_ANG = 0.45, 2.0
ARRIVE = 0.12


class Motion(Node):
    def __init__(self):
        super().__init__('motion')
        self.pose = None  # x, y, yaw
        self.state = {}
        self.steps = []   # queue of ('go', place) / ('wiggle'|'spin'|'wait', seconds)
        self.step_t0 = None
        self.wander_at = self.get_clock().now()
        self.pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        self.activity_pub = self.create_publisher(String, '/robopet/activity', 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(String, '/robopet/action', self.on_action, 10)
        self.create_subscription(String, '/robopet/state', self.on_state, 10)
        self.create_timer(0.05, self.tick)
        self.last_activity = ''
        self.get_logger().info('motion ready')

    # ---- inputs ------------------------------------------------------------
    def on_odom(self, m):
        p, q = m.pose.pose.position, m.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        self.pose = (p.x, p.y, yaw)

    def on_state(self, m):
        try:
            self.state = json.loads(m.data)
        except ValueError:
            pass

    def on_action(self, m):
        try:
            name = json.loads(m.data)['name']
        except (ValueError, KeyError, TypeError):
            return
        plans = {
            'feed': [('go', 'bowl'), ('wiggle', 3.0)],
            'play': [('go', 'toy'), ('spin', 5.0)],
            'medicine': [('wiggle', 2.0)],
            'sleep': [('go', 'bed'), ('wait', 1e9)],
            'wake': [('wiggle', 1.5), ('go', 'home')],
        }
        if name in plans:
            self.set_plan(plans[name])

    def set_plan(self, steps):
        self.steps = list(steps)
        self.step_t0 = None

    # ---- main loop ---------------------------------------------------------
    def tick(self):
        if self.pose is None:
            return
        if not self.steps:
            self.decide()
        if not self.steps:
            self.drive(0.0, 0.0)
            self.say('resting')
            return
        kind, arg = self.steps[0]
        now = self.get_clock().now()
        if self.step_t0 is None:
            self.step_t0 = now
        t = (now - self.step_t0).nanoseconds / 1e9
        if kind == 'go':
            self.say(f'walking to the {arg}' if arg in PLACES else 'walking')
            if self.go_to(PLACES[arg] if arg in PLACES else arg):
                self.next_step()
        elif kind == 'wiggle':
            self.say('wiggling happily')
            self.drive(0.0, 1.5 * math.sin(t * 6.0))
            if t > arg:
                self.next_step()
        elif kind == 'spin':
            self.say('playing: spinning around')
            self.drive(0.12, 1.0)
            if t > arg:
                self.next_step()
        elif kind == 'wait':
            self.say('sleeping in bed' if self.state.get('sleeping') else 'waiting')
            self.drive(0.0, 0.0)
            if not self.state.get('sleeping') and t > 2.0:  # woke up by itself
                self.next_step()

    def next_step(self):
        self.steps.pop(0)
        self.step_t0 = None
        self.drive(0.0, 0.0)

    def decide(self):
        """Nothing to do: choose something from how the pet feels."""
        st = self.state
        now = self.get_clock().now()
        if st.get('sleeping'):
            self.set_plan([('go', 'bed'), ('wait', 1e9)])
        elif st.get('food', 100) < 35 and self.dist(PLACES['bowl']) > 0.3:
            self.set_plan([('go', 'bowl'), ('wait', 8.0)])
        elif st.get('energy', 100) < 25 and self.dist(PLACES['bed']) > 0.3:
            self.set_plan([('go', 'bed'), ('wait', 8.0)])
        elif (now - self.wander_at).nanoseconds / 1e9 > 15.0:
            self.wander_at = now
            if random.random() < 0.6:
                self.set_plan([('go', (random.uniform(-1.5, 1.5), random.uniform(-1.8, 0.8)))])

    # ---- driving -----------------------------------------------------------
    def dist(self, goal):
        return math.hypot(goal[0] - self.pose[0], goal[1] - self.pose[1])

    def go_to(self, goal):
        """Turn towards the goal, then drive to it. Returns True on arrival."""
        d = self.dist(goal)
        if d < ARRIVE:
            return True
        want = math.atan2(goal[1] - self.pose[1], goal[0] - self.pose[0])
        err = math.atan2(math.sin(want - self.pose[2]), math.cos(want - self.pose[2]))
        ang = max(-MAX_ANG, min(MAX_ANG, 1.8 * err))
        lin = MAX_LIN * max(0.0, 1 - abs(err) / 0.6) * min(1.0, d / 0.4 + 0.3)
        self.drive(lin, ang)
        return False

    def drive(self, lin, ang):
        m = TwistStamped()
        m.header.stamp = self.get_clock().now().to_msg()
        m.twist.linear.x, m.twist.angular.z = float(lin), float(ang)
        self.pub.publish(m)

    def say(self, text):
        if text != self.last_activity:
            self.last_activity = text
            self.activity_pub.publish(String(data=text))


def main():
    rclpy.init()
    node = Motion()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()
