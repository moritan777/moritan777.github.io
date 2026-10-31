#!/usr/bin/env bash
set -euo pipefail
APP=/home/hems/simplehems-server-v2
SERVER="$APP/backend/server.py"
FRONT="$APP/frontend/src.jsx"
CSS="$APP/frontend/style.css"
MONITOR="$APP/tools/mwd701_monitor_test_v2.py"
RUN=/run/simplehems-doorphone

for f in "$SERVER" "$FRONT" "$CSS" "$MONITOR"; do [ -f "$f" ] || { echo "not found: $f" >&2; exit 1; }; done
cp -an "$SERVER" "$SERVER.bak_snapshot_integration"
cp -an "$FRONT" "$FRONT.bak_snapshot_integration"
cp -an "$CSS" "$CSS.bak_snapshot_integration"
install -d -o hems -g hems -m 0755 "$RUN"

python3 - "$SERVER" "$FRONT" "$CSS" <<'PY'
from pathlib import Path
import sys
server,front,css=map(Path,sys.argv[1:4])

s=server.read_text(encoding='utf-8')
if '/api/doorphone/snapshot' not in s:
    anchors=[
      "if self.path=='/api/doorphone/event':return self.send_data(doorphone_add(body))",
      'if self.path == "/api/doorphone/event": return self.send_data(doorphone_add(body))',
    ]
    a=next((x for x in anchors if x in s),None)
    if not a: raise SystemExit('backend event route anchor not found; no files written')
    indent=a[:len(a)-len(a.lstrip())]
    add=(indent+"if self.path=='/api/doorphone/snapshot':\n"+
         indent+" open('/run/simplehems-doorphone/snapshot.request','w').write(datetime.now(timezone.utc).isoformat())\n"+
         indent+" return self.send_data({'ok':True,'queued':True})\n"+
         indent+a.lstrip())
    s=s.replace(a,add,1)

f=front.read_text(encoding='utf-8')
start=f.find('function DoorphonePage() {');end=f.find('\nfunction CameraPage() {',start)
if start<0 or end<0: raise SystemExit('DoorphonePage boundary not found; no files written')
seg=f[start:end]
if 'requestDoorphoneSnapshot' not in seg:
    state='  const [snapshotMsg, setSnapshotMsg] = useState("");\n'
    pos=seg.find('\n',seg.find('function DoorphonePage() {'))+1
    seg=seg[:pos]+state+seg[pos:]
    load_anchor='  const load = async () => {'
    p=seg.find(load_anchor)
    if p<0: raise SystemExit('Doorphone load anchor not found; no files written')
    fn='''  const requestDoorphoneSnapshot = async () => {
    try { setSnapshotMsg("画像取得を開始しました"); await api("/api/doorphone/snapshot", {method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}); setTimeout(load, 6000); }
    catch (e) { setSnapshotMsg("画像取得失敗: " + e.message); }
  };
'''
    seg=seg[:p]+fn+seg[p:]
    image_anchor='{data.latest ?'
    p=seg.find(image_anchor)
    if p<0: raise SystemExit('latest image anchor not found; no files written')
    ui='<div className="doorphoneSnapshotActions"><button onClick={requestDoorphoneSnapshot}>現在の玄関画像を取得</button>{snapshotMsg && <small>{snapshotMsg}</small>}</div>\n        '
    seg=seg[:p]+ui+seg[p:]
    f=f[:start]+seg+f[end:]

c=css.read_text(encoding='utf-8')
mark='/* doorphone snapshot integration */'
if mark not in c:
    c+='''\n\n/* doorphone snapshot integration */
.doorphoneSnapshotActions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0}.doorphoneSnapshotActions button{min-height:40px}.doorphoneSnapshotActions small{opacity:.78}@media(max-width:650px){.doorphoneSnapshotActions{align-items:stretch;flex-direction:column}.doorphoneSnapshotActions button{width:100%}}\n'''

server.write_text(s,encoding='utf-8');front.write_text(f,encoding='utf-8');css.write_text(c,encoding='utf-8')
print('backend marker:', '/api/doorphone/snapshot' in s)
print('frontend marker:', 'requestDoorphoneSnapshot' in f)
PY

cat > /etc/systemd/system/simplehems-doorphone-snapshot.service <<'EOF'
[Unit]
Description=SimpleHEMS VL-MWD701 one-shot snapshot
After=network-online.target simplehems.service
Requires=simplehems.service

[Service]
Type=oneshot
ExecStartPre=-/usr/bin/systemctl stop simplehems-doorphone.service
ExecStartPre=/usr/bin/rm -f /run/simplehems-doorphone/snapshot.request
ExecStart=/usr/sbin/runuser -u hems -- /home/hems/simplehems-server-v2/.venv/bin/python /home/hems/simplehems-server-v2/tools/mwd701_monitor_test_v2.py --host 192.168.11.29 --user Smartphone1 --phone-mac 12:63:0f:a9:4e:3d --base-mac 08:00:23:cd:77:3c --output /home/hems/mwd701_monitor.jpg --api-event http://127.0.0.1:8787/api/doorphone/event
ExecStartPost=-/usr/bin/systemctl start simplehems-doorphone.service
TimeoutStartSec=45
EOF

cat > /etc/systemd/system/simplehems-doorphone-snapshot.path <<'EOF'
[Unit]
Description=Watch for SimpleHEMS doorphone snapshot requests
After=simplehems.service

[Path]
PathExists=/run/simplehems-doorphone/snapshot.request
Unit=simplehems-doorphone-snapshot.service

[Install]
WantedBy=multi-user.target
EOF

"$APP/.venv/bin/python" -m py_compile "$SERVER" "$MONITOR"
cd "$APP/frontend"
npm run build
systemctl daemon-reload
systemctl enable --now simplehems-doorphone-snapshot.path
systemctl restart simplehems.service
systemctl start simplehems-doorphone.service
printf '\nSnapshot API and UI installed.\n'
systemctl --no-pager --full status simplehems-doorphone-snapshot.path | sed -n '1,12p'
