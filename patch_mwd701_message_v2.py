#!/usr/bin/env python3
from pathlib import Path
import py_compile
import shutil
import sys

p = Path('mwd701_pair_diagnostic.py')
if not p.is_file():
    raise SystemExit('mwd701_pair_diagnostic.py not found; run from /home/hems/simplehems-server-v2')
s = p.read_text(encoding='utf-8')
backup = p.with_suffix('.py.bak_before_xml')
if not backup.exists():
    shutil.copy2(p, backup)

old = '''    body = f'Register:MAC={ctx.mac};Name="{ctx.name}"\\r\\n'
    request = (
'''
new = '''    # VL-MWD701 pure-app PCAP: NUL + XML + NUL.
    body_bytes = (
        b"\\x00"
        + b'<?xml version="1.0" encoding="UTF-8"?>'
        + b"<REGISTER><MAC>"
        + ctx.mac.encode("ascii")
        + b"</MAC></REGISTER>"
        + b"\\x00"
    )
    request_head = (
'''
if old not in s:
    raise SystemExit('old body block not found; no changes made')
s = s.replace(old, new, 1)

old = '''        "Allow: INVITE,ACK,CANCEL,BYE,INFO,MESSAGE,NOTIFY,UPDATE\\r\\n"
        "Content-Type: application/text\\r\\n"
        f"User-Agent: {USER_AGENT}\\r\\n"
        f"Content-Length: {len(body.encode('utf-8'))}\\r\\n\\r\\n{body}"
    )
    log("sip.message.send", base=ctx.base_ip, local_port=ctx.local_port,
        body=body.rstrip(), bytes=len(request.encode("utf-8")))
    sock.sendto(request.encode("utf-8"), (ctx.base_ip, SIP_PORT))
'''
new = '''        "Allow: BYE,NOTIFY\\r\\n"
        "Content-Type: application/text\\r\\n"
        f"User-Agent: {USER_AGENT}\\r\\n"
        f"Content-Length: {len(body_bytes)}\\r\\n\\r\\n"
    )
    request = request_head.encode("utf-8") + body_bytes
    log("sip.message.send", base=ctx.base_ip, local_port=ctx.local_port,
        body_hex=body_bytes.hex(), content_length=len(body_bytes), bytes=len(request))
    sock.sendto(request, (ctx.base_ip, SIP_PORT))
'''
if old not in s:
    raise SystemExit('old request block not found; restore backup if needed')
s = s.replace(old, new, 1)

old = '''    log("sip.message.response", peer=peer[0], status=status, assigned_terminal=assigned,
        headers={"PSN-Notify-PSnum": psnum})
'''
new = '''    log("sip.message.response", peer=peer[0], status=status, assigned_terminal=assigned,
        headers={"PSN-Notify-PSnum": psnum}, response=response[:8192])
'''
if old not in s:
    raise SystemExit('old response log block not found; restore backup if needed')
s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
py_compile.compile(str(p), doraise=True)
print(f'Patched: {p}')
print(f'Backup : {backup}')
print('Expected MESSAGE Content-Length for 12-char MAC: 84')
