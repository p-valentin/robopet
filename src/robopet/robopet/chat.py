"""Terminal chat with the pet. Type to talk. /status shows the needs. Ctrl+C quits."""
import json
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

BAR = 20


def bars(st):
    out = []
    for k in ('food', 'energy', 'happiness', 'health'):
        n = round(st[k] / 100 * BAR)
        out.append(f'{k:<10}{"#" * n}{"." * (BAR - n)} {st[k]:>3}')
    out.append(f'mood: {st["mood"]}' + ('  (sleeping)' if st['sleeping'] else ''))
    return '\n'.join(out)


class Chat(Node):
    def __init__(self):
        super().__init__('chat')
        self.state = None
        self.say = self.create_publisher(String, '/robopet/say', 10)
        self.create_subscription(String, '/robopet/reply', lambda m: print(f'\n🐾 {m.data}\n> ', end='', flush=True), 10)
        self.create_subscription(String, '/robopet/state', lambda m: setattr(self, 'state', json.loads(m.data)), 10)
        self.create_subscription(String, '/robopet/action_result', self.on_result, 10)

    def on_result(self, msg):
        r = json.loads(msg.data)
        mark = '✔' if r['ok'] else '✘'
        print(f'\n   [{mark} {r["name"]}: {r["note"]}]\n> ', end='', flush=True)


def main():
    rclpy.init()
    node = Chat()
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    try:
        while True:
            text = input('> ').strip()
            if text == '/status':
                print(bars(node.state) if node.state else '(no state yet: is the `needs` node running?)')
            elif text:
                node.say.publish(String(data=text))
    except (KeyboardInterrupt, EOFError):
        pass
    rclpy.try_shutdown()
