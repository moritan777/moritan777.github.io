#!/usr/bin/env bash
set -euo pipefail
APP=/home/hems/simplehems-server-v2
MONITOR="$APP/tools/mwd701_monitor_test_v2.py"
PY="$APP/.venv/bin/python"
RUN=/run/simplehems-doorphone

[ -f "$MONITOR" ] || { echo "not found: $MONITOR" >&2; exit 1; }
[ -x "$PY" ] || { echo "not found: $PY" >&2; exit 1; }
"$PY" -m py_compile "$MONITOR"
install -d -o hems -g hems -m 0755 "$RUN"
rm -f "$RUN/snapshot.request"

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
Description=Watch SimpleHEMS doorphone snapshot requests
After=simplehems.service
Requires=simplehems.service

[Path]
PathExists=/run/simplehems-doorphone/snapshot.request
Unit=simplehems-doorphone-snapshot.service

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now simplehems-doorphone-snapshot.path
systemctl start simplehems-doorphone.service || true
printf '%s\n' '--- path ---'
systemctl is-active simplehems-doorphone-snapshot.path
printf '%s\n' '--- doorphone ---'
systemctl is-active simplehems-doorphone.service
printf '%s\n' 'installed'
