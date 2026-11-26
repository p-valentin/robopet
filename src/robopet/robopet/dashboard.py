"""A web page for the pet: need bars, what it is doing, and a chat box.

Open http://localhost:8770 in any browser on this laptop (the container shares its network).
Uses only the Python standard library.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robopet</title><style>
:root{--bg:#f6f4ee;--card:#fff;--ink:#222;--mut:#777;--line:#ddd}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--card:#222;--ink:#eee;--mut:#999;--line:#444}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px system-ui,sans-serif;display:flex;justify-content:center}
main{width:100%;max-width:560px;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}
#face{font-size:64px;text-align:center}#mood{text-align:center;color:var(--mut)}
.row{display:flex;align-items:center;gap:10px;margin:8px 0}.row span{width:84px}
.bar{flex:1;height:14px;background:var(--line);border-radius:8px;overflow:hidden}.bar i{display:block;height:100%;border-radius:8px;transition:width .5s}
#log{height:240px;overflow:auto;display:flex;flex-direction:column;gap:6px}
.u{align-self:flex-end;background:#2f6fed;color:#fff;border-radius:12px;padding:6px 10px;max-width:80%}
.p{align-self:flex-start;background:var(--line);border-radius:12px;padding:6px 10px;max-width:80%}
.s{align-self:center;color:var(--mut);font-size:13px}
form{display:flex;gap:8px;margin-top:10px}input{flex:1;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font-size:16px}
button{padding:10px 14px;border:0;border-radius:10px;background:#2f6fed;color:#fff;font-size:16px}
.quick button{background:var(--line);color:var(--ink);margin:4px 4px 0 0}
</style></head><body><main>
<div class="card"><div id="face">🙂</div><div id="mood">...</div><div id="act" style="text-align:center;color:var(--mut)"></div></div>
<div class="card" id="bars"></div>
<div class="card"><div id="log"></div>
<div class="quick"><button data-a="feed">🍖 Feed</button><button data-a="play">🎾 Play</button><button data-a="medicine">💊 Medicine</button><button data-a="sleep">🌙 Sleep</button><button data-a="wake">☀️ Wake</button></div>
<form id="f"><input id="t" placeholder="Say something..." autocomplete="off"><button>Send</button></form></div>
</main><script>
const FACE={happy:'😄',ok:'🙂',hungry:'😠',tired:'🥱',sad:'😢',sick:'🤒',sleeping:'😴'};
const COL={food:'#e07b39',energy:'#e0b739',happiness:'#d94f8c',health:'#3aa655'};
const NAMES={food:'🍖 Food',energy:'⚡ Energy',happiness:'💛 Happy',health:'❤️ Health'};
let seen=0,pending=false;
function say(t){fetch('/api/say',{method:'POST',body:JSON.stringify({text:t})});add('u',t);pending=true}
function add(c,t){const d=document.createElement('div');d.className=c;d.textContent=t;const l=document.getElementById('log');l.appendChild(d);l.scrollTop=l.scrollHeight}
document.getElementById('f').onsubmit=e=>{e.preventDefault();const i=document.getElementById('t');if(i.value.trim()){say(i.value.trim());i.value=''}};
document.querySelectorAll('.quick button').forEach(b=>b.onclick=()=>{fetch('/api/act',{method:'POST',body:JSON.stringify({name:b.dataset.a})});pending=true});
async function poll(){try{const r=await (await fetch('/api/state')).json();const s=r.state||{};
 document.getElementById('face').textContent=FACE[s.mood]||'🙂';
 document.getElementById('mood').textContent=s.mood?('mood: '+s.mood):'waiting for the pet...';
 document.getElementById('act').textContent=(r.activity||'')+(pending?'  ·  thinking...':'');
 document.getElementById('bars').innerHTML=['food','energy','happiness','health'].map(k=>`<div class="row"><span>${NAMES[k]}</span><div class="bar"><i style="width:${s[k]??0}%;background:${COL[k]}"></i></div><b>${s[k]??'-'}</b></div>`).join('');
 for(const m of r.log.slice(seen)){add(m[0],m[1]);if(m[0]=='p')pending=false} seen=r.log.length}catch(e){}
 setTimeout(poll,1000)}
poll();
</script></body></html>"""


class Dashboard(Node):
    def __init__(self):
        super().__init__('dashboard')
        port = int(self.declare_parameter('port', 8770).value)
        self.state, self.activity, self.log = {}, '', []
        self.lock = threading.Lock()
        self.say_pub = self.create_publisher(String, '/robopet/say', 10)
        self.action_pub = self.create_publisher(String, '/robopet/action', 10)
        self.did_pub = self.create_publisher(String, '/robopet/did', 10)
        self.create_subscription(String, '/robopet/state', lambda m: self.set('state', json.loads(m.data)), 10)
        self.create_subscription(String, '/robopet/activity', lambda m: self.set('activity', m.data), 10)
        self.create_subscription(String, '/robopet/reply', lambda m: self.add('p', m.data), 10)
        self.create_subscription(String, '/robopet/action_result', self.on_result, 10)
        node = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, code, body, ctype):
                self.send_response(code)
                self.send_header('Content-Type', ctype)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == '/api/state':
                    with node.lock:
                        body = json.dumps({'state': node.state, 'activity': node.activity, 'log': node.log})
                    self.send(200, body.encode(), 'application/json')
                else:
                    self.send(200, PAGE.encode(), 'text/html; charset=utf-8')

            def do_POST(self):
                n = int(self.headers.get('Content-Length', 0))
                try:
                    body = json.loads(self.rfile.read(n))
                except ValueError:
                    return self.send(400, b'bad', 'text/plain')
                if self.path == '/api/act' and body.get('name') in ('feed', 'play', 'medicine', 'sleep', 'wake'):
                    # buttons: do it now (no waiting for the LLM), then let the pet say something about it
                    node.action_pub.publish(String(data=json.dumps({'name': body['name']})))
                    node.did_pub.publish(String(data=json.dumps({'name': body['name']})))
                elif 'text' in body:
                    node.say_pub.publish(String(data=str(body['text'])[:300]))
                else:
                    return self.send(400, b'bad', 'text/plain')
                self.send(200, b'ok', 'text/plain')

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.get_logger().info(f'dashboard at http://localhost:{port}')

    def set(self, key, value):
        with self.lock:
            setattr(self, key, value)

    def add(self, kind, text):
        with self.lock:
            self.log.append([kind, text])
            self.log = self.log[-100:]

    def on_result(self, m):
        r = json.loads(m.data)
        self.add('s', f'{"✔" if r["ok"] else "✘"} {r["name"]}: {r["note"]}')


def main():
    rclpy.init()
    node = Dashboard()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.server.shutdown()
    node.destroy_node()
    rclpy.try_shutdown()
