#!/usr/bin/env bash
set -euo pipefail
APP=/home/hems/simplehems-server-v2
PROBE="$APP/tools/doorphone_probe_integrated.py"
PY="$APP/.venv/bin/python"
UNIT=/etc/systemd/system/simplehems-doorphone.service
BACKUP="$UNIT.bak_before_install"

[ -f "$PROBE" ] || { echo "not found: $PROBE" >&2; exit 1; }
[ -x "$PY" ] || { echo "not found: $PY" >&2; exit 1; }
"$PY" -m py_compile "$PROBE"
"$PY" -c 'from cryptography.hazmat.primitives.ciphers import Cipher' >/dev/null

if [ -f "$UNIT" ] && [ ! -f "$BACKUP" ]; then cp -a "$UNIT" "$BACKUP"; fi
cat > "$UNIT" <<'EOF'
[Unit]
Description=SimpleHEMS Panasonic VL-MWD701 SIP client
After=network-online.target simplehems.service
Wants=network-online.target
Requires=simplehems.service

[Service]
Type=simple
User=hems
Group=hems
WorkingDirectory=/home/hems/simplehems-server-v2
ExecStart=/home/hems/simplehems-server-v2/.venv/bin/python /home/hems/simplehems-server-v2/tools/doorphone_probe_integrated.py --ip 192.168.11.29 --mac 12:63:0f:a9:4e:3d --phone-id Smartphone1 --api http://127.0.0.1:8787/api/doorphone/state
Restart=on-failure
RestartSec=10
TimeoutStopSec=10
KillSignal=SIGINT
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable simplehems-doorphone.service
systemctl restart simplehems-doorphone.service
sleep 2
systemctl --no-pager --full status simplehems-doorphone.service
