#!/usr/bin/env python3
from pathlib import Path
import re, shutil, py_compile

p = Path('mwd701_pair_diagnostic.py')
if not p.is_file():
    raise SystemExit('mwd701_pair_diagnostic.py が見つかりません')
bak = Path('mwd701_pair_diagnostic.py.bak_before_pcap_v3')
if not bak.exists():
    shutil.copy2(p, bak)
s = p.read_text(encoding='utf-8')

# Pure VL-MWD701 PCAP body is literal ASCII "00" + XML, total 84 bytes.
s, n = re.subn(
    r'''(?m)^\s*xml = f'\<\?xml version="1\.0" encoding="UTF-8"\?\>\<REGISTER\>\<MAC\>\{ctx\.mac\}\</MAC\>\</REGISTER\>'\n\s*body_bytes = b"\\x00" \+ xml\.encode\("ascii"\) \+ b"\\x00"\n\s*body = body_bytes\.decode\("latin-1"\)''',
    '''    xml = f'<?xml version="1.0" encoding="UTF-8"?><REGISTER><MAC>{ctx.mac}</MAC></REGISTER>'\n    body_bytes = ("00" + xml).encode("ascii")\n    body = body_bytes.decode("ascii")''', s)
if n == 0:
    s, n = re.subn(
        r'''(?m)^\s*body = f'00\<\?xml version="1\.0" encoding="UTF-8"\?\>\<REGISTER\>\<MAC\>\{ctx\.mac\}\</MAC\>\</REGISTER\>'$''',
        '''    body = f'00<?xml version="1.0" encoding="UTF-8"?><REGISTER><MAC>{ctx.mac}</MAC></REGISTER>'\n    body_bytes = body.encode("ascii")''', s)
if n == 0 and 'body_bytes = ("00" + xml).encode("ascii")' not in s:
    raise SystemExit('MESSAGE本文の対象コードが見つかりません')

# Ensure the pure-app Allow header.
s = s.replace('Allow: INVITE,ACK,CANCEL,BYE,INFO,MESSAGE,NOTIFY,UPDATE\\r\\n',
              'Allow: BYE,NOTIFY\\r\\n')

# Add Smartphone1 option if the old terminal option remains.
s = re.sub(
    r'\s*ap\.add_argument\("--terminal"[^\n]*\)\n',
    '\n    ap.add_argument("--username", default="Smartphone1", help="VL-MWD701 PCAP REGISTER username")\n', s)
if '--username' not in s:
    marker = '    ap.add_argument("--observe"'
    if marker in s:
        s = s.replace(marker, '    ap.add_argument("--username", default="Smartphone1", help="VL-MWD701 PCAP REGISTER username")\n' + marker, 1)

old_block = '''    assigned = send_pair_message(msg_sock, msg_ctx)\n    msg_sock.close()\n    terminal = assigned or args.terminal\n    if terminal is None or not 21 <= terminal <= 28:\n        log("fatal", message="No valid terminal 21..28; use --terminal only if known from capture")\n        return 4\n'''
new_block = '''    assigned = send_pair_message(msg_sock, msg_ctx)\n    msg_sock.close()\n    username = str(assigned) if assigned is not None else args.username\n    log("pair.username", username=username, source="PSN-Notify-PSnum" if assigned is not None else "capture-default")\n'''
if old_block in s:
    s = s.replace(old_block, new_block, 1)
elif 'No valid terminal 21..28' in s:
    raise SystemExit('端末番号ブロックの形が想定外です')

# REGISTER uses SmartphoneN, not numeric terminal slots.
s = s.replace('def build_register(ctx: SipContext, terminal: int, cseq: int,',
              'def build_register(ctx: SipContext, username: str, cseq: int,')
s = s.replace('digest_response(str(terminal),', 'digest_response(username,')
s = s.replace('{terminal}@{ctx.base_ip}', '{username}@{ctx.base_ip}')
s = s.replace('username="{terminal}"', 'username="{username}"')
s = s.replace('def register(sock: socket.socket, ctx: SipContext, terminal: int):',
              'def register(sock: socket.socket, ctx: SipContext, username: str):')
s = s.replace('build_register(ctx, terminal, 1)', 'build_register(ctx, username, 1)')
s = s.replace('build_register(ctx, terminal, cseq, auth)', 'build_register(ctx, username, cseq, auth)')
s = s.replace('register(reg_sock, reg_ctx, terminal)', 'register(reg_sock, reg_ctx, username)')
s = s.replace('log("pair.sip_registered", terminal=terminal,',
              'log("pair.sip_registered", username=username,')
s = s.replace('log("diagnostic.complete", terminal=terminal,',
              'log("diagnostic.complete", username=username,')

p.write_text(s, encoding='utf-8')
py_compile.compile(str(p), doraise=True)
print('Patched:', p)
print('Backup :', bak)
print('Checks : ASCII 00+XML / Smartphone1 / Allow BYE,NOTIFY')
