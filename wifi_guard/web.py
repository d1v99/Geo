"""Small local dashboard: live status plus arm and disarm buttons."""

from __future__ import annotations

import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WiFi Guard</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--text:#16181d;--muted:#6b7280;--line:#e3e5ea;--ok:#15803d;--bad:#b91c1c;--warn:#b45309;--accent:#1d4ed8}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b22;--text:#eceef2;--muted:#9aa1ad;--line:#2a2e38;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--accent:#60a5fa}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:22px;margin:0 0 16px}h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:24px 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.state{font-size:26px;font-weight:700}.sub{color:var(--muted);font-size:14px;margin-top:2px}
button{font:inherit;font-weight:600;border:0;border-radius:10px;padding:12px 18px;margin-top:14px;color:#fff;background:var(--accent);cursor:pointer;width:100%}
button.off{background:var(--bad)}
.row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-top:1px solid var(--line)}.row:first-child{border-top:0;padding-top:0}.row:last-child{padding-bottom:0}
.bar{height:6px;border-radius:3px;background:var(--line);margin-top:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--ok)}
.motion{color:var(--bad);font-weight:600}.quiet{color:var(--ok)}.calibrating,.offline{color:var(--warn)}
.time{color:var(--muted);font-size:13px;white-space:nowrap}.empty{color:var(--muted)}
.note{color:var(--warn);font-size:14px;margin-top:10px}
</style></head><body><main>
<h1>WiFi Guard</h1>
<div class="card"><div class="state" id="state">...</div><div class="sub" id="sub"></div>
<button id="toggle">...</button><div class="note" id="note"></div></div>
<h2>Sensors</h2><div class="card" id="sensors"></div>
<h2>Recent activity</h2><div class="card" id="events"></div>
</main><script>
let armed=false;
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function refresh(){
  let s;try{s=await (await fetch('/api/status')).json()}catch(e){$('state').textContent='Hub unreachable';return}
  armed=s.armed;
  $('state').textContent=!s.armed?'Disarmed':s.active?'Armed':'Arming...';
  $('sub').textContent=!s.armed?'Watching, but no alerts will be sent.':s.active?'Alerts go to your phone.':'Active in '+s.active_in_s+' s. Time to leave.';
  $('toggle').textContent=s.armed?'Disarm':'Arm';$('toggle').className=s.armed?'off':'';
  $('note').textContent=s.alerts_configured?'':'No ntfy topic set, so alerts are only logged.';
  $('sensors').innerHTML=s.sensors.length?s.sensors.map(x=>{
    const pct=Math.max(0,Math.min(100,100*x.level/(2*x.threshold)));
    return '<div class="row"><div style="flex:1"><div>'+esc(x.name)+'</div><div class="bar"><i style="width:'+pct+'%;'+(x.level>x.threshold?'background:var(--bad)':'')+'"></i></div></div><div class="'+esc(x.state)+'">'+esc(x.state)+'</div></div>'}).join('')
    +(s.phones_nearby?'<div class="row"><div>Phones heard nearby</div><div>'+s.phones_nearby+'</div></div>':''):'<div class="empty">No sensors reporting yet.</div>';
  $('events').innerHTML=s.events.length?s.events.map(e=>'<div class="row"><div>'+esc(e.text)+'</div><div class="time">'+new Date(e.t*1000).toLocaleTimeString()+'</div></div>').join(''):'<div class="empty">Nothing yet.</div>';
}
$('toggle').onclick=async()=>{
  const headers={};let pin=sessionStorage.getItem('pin');
  for(let attempt=0;attempt<2;attempt++){
    if(pin)headers['X-Pin']=pin;
    const r=await fetch(armed?'/api/disarm':'/api/arm',{method:'POST',headers});
    if(r.status!==403)break;
    pin=prompt('PIN');if(!pin)break;sessionStorage.setItem('pin',pin);
  }
  refresh();
};
refresh();setInterval(refresh,2000);
</script></body></html>
"""


def serve(hub, host: str, port: int, pin: str = "") -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload).encode(), "application/json")

        def do_GET(self) -> None:
            if self.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif self.path == "/api/status":
                self._json(200, hub.status())
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path not in ("/api/arm", "/api/disarm"):
                self._json(404, {"error": "not found"})
                return
            # A custom header cannot be set by a cross-site form, which blocks drive-by requests.
            if pin and not hmac.compare_digest(self.headers.get("X-Pin", ""), pin):
                self._json(403, {"error": "wrong pin"})
                return
            if self.path == "/api/arm":
                hub.arm()
            else:
                hub.disarm()
            self._json(200, hub.status())

        def log_message(self, *args) -> None:
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="web").start()
    return server
