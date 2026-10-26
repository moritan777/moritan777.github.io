#!/usr/bin/env python3
from pathlib import Path
import shutil, py_compile, re

src = Path('mwd701_pair_diagnostic.py.bak_exact')
dst = Path('mwd701_pair_diagnostic.py')
if not src.is_file():
    raise SystemExit('mwd701_pair_diagnostic.py.bak_exact が見つかりません')
text = src.read_text(encoding='utf-8')
lines = text.splitlines(keepends=True)

def find_line(start, predicate):
    for i in range(start, len(lines)):
        if predicate(lines[i]):
            return i
    raise SystemExit('対象行が見つかりません')

# 1) Replace the body builder inside send_pair_message without relying on line numbers.
f = find_line(0, lambda x: x.startswith('def send_pair_message('))
body_start = find_line(f, lambda x: 'body_bytes = (' in x or "body = f'Register:MAC=" in x)
head = find_line(body_start, lambda x: 'request_head = (' in x or 'request = (' in x)
indent = '    '
lines[body_start:head] = [
    indent + "body_bytes = (b\"00\" + f'<?xml version=\"1.0\" encoding=\"UTF-8\"?><REGISTER><MAC>{ctx.mac}</MAC></REGISTER>'.encode(\"ascii\"))\n"
]

# Refresh text/lines and force pure-app Allow header.
text = ''.join(lines).replace(
    'Allow: INVITE,ACK,CANCEL,BYE,INFO,MESSAGE,NOTIFY,UPDATE\\r\\n',
    'Allow: BYE,NOTIFY\\r\\n')
lines = text.splitlines(keepends=True)

# 2) Replace old terminal-number gate with Smartphone1 fallback.
assigned_i = find_line(0, lambda x: 'assigned = send_pair_message(msg_sock, msg_ctx)' in x)
regsock_i = find_line(assigned_i, lambda x: 'reg_sock = socket.socket(' in x)
# Keep assigned line and msg_sock.close(), replace everything after close until reg_sock.
close_i = find_line(assigned_i, lambda x: 'msg_sock.close()' in x)
lines[close_i + 1:regsock_i] = [
    '    username = str(assigned) if assigned is not None else "Smartphone1"\n',
    '    log("pair.username", username=username, source="PSN-Notify-PSnum" if assigned is not None else "capture-default")\n',
    '\n',
]
text = ''.join(lines)

# 3) REGISTER path uses SmartphoneN strings, not integer terminal slots.
replacements = [
    ('def build_register(ctx: SipContext, terminal: int, cseq: int,',
     'def build_register(ctx: SipContext, username: str, cseq: int,'),
    ('digest_response(str(terminal),', 'digest_response(username,'),
    ('{terminal}@{ctx.base_ip}', '{username}@{ctx.base_ip}'),
    ('username="{terminal}"', 'username="{username}"'),
    ('def register(sock: socket.socket, ctx: SipContext, terminal: int):',
     'def register(sock: socket.socket, ctx: SipContext, username: str):'),
    ('build_register(ctx, terminal, 1)', 'build_register(ctx, username, 1)'),
    ('build_register(ctx, terminal, cseq, auth)', 'build_register(ctx, username, cseq, auth)'),
    ('register(reg_sock, reg_ctx, terminal)', 'register(reg_sock, reg_ctx, username)'),
    ('log("pair.sip_registered", terminal=terminal,',
     'log("pair.sip_registered", username=username,'),
    ('log("diagnostic.complete", terminal=terminal,',
     'log("diagnostic.complete", username=username,'),
]
for old, new in replacements:
    text = text.replace(old, new)

# Remove obsolete --terminal argument if present. No --username option is needed yet;
# Smartphone1 is deliberately fixed to match this capture.
text = re.sub(r'^\s*ap\.add_argument\("--terminal"[^\n]*\)\n', '', text, flags=re.M)

# Safety checks before writing.
required = [
    'body_bytes = (b"00" +',
    'Allow: BYE,NOTIFY',
    'username = str(assigned) if assigned is not None else "Smartphone1"',
    'register(reg_sock, reg_ctx, username)',
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit('修復後チェック失敗: ' + ', '.join(missing))
if 'No valid terminal 21..28' in text:
    raise SystemExit('旧端末番号判定が残っています')

tmp = Path('mwd701_pair_diagnostic.py.rebuilt')
tmp.write_text(text, encoding='utf-8')
py_compile.compile(str(tmp), doraise=True)
shutil.copy2(dst, Path('mwd701_pair_diagnostic.py.broken_before_rebuild'))
tmp.replace(dst)
print('Rebuilt:', dst)
print('Source :', src)
print('Broken backup: mwd701_pair_diagnostic.py.broken_before_rebuild')
print('Checks : ASCII 00+XML / Smartphone1 / Allow BYE,NOTIFY / py_compile OK')
