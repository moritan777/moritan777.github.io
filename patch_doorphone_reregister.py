#!/usr/bin/env python3
from pathlib import Path
import shutil, sys

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else '/home/hems/simplehems-server-v2/tools/doorphone_probe_integrated.py')
if not TARGET.exists():
    raise SystemExit(f'not found: {TARGET}')

text = TARGET.read_text(encoding='utf-8')
marker = 'Re-REGISTER every 20 seconds'
if marker in text:
    print('already patched:', TARGET)
    raise SystemExit(0)

old = """ print('REGISTER successful. Waiting for NOTIFY. Ctrl+C to stop.',flush=True)
 try:
  while True:recv_until(sock,60,pw,a.api,phone)
 except KeyboardInterrupt:pass
 finally:sock.close()"""

new = """ print('REGISTER successful. Waiting for NOTIFY. Re-REGISTER every 20 seconds. Ctrl+C to stop.',flush=True)
 cseq=2
 next_refresh=time.monotonic()+20
 try:
  while True:
   wait=max(0.1,min(1.0,next_refresh-time.monotonic()))
   packets,_=recv_until(sock,wait,pw,a.api,phone)
   new_challenge=next((h.get('www-authenticate',[None])[0] for st,h,*_ in packets if st.startswith('SIP/2.0 401')),None)
   if new_challenge:
    challenge=new_challenge
    cseq+=1
    retry=register_request(base,local,port,phone,cseq,cid,tag,challenge,a.mac)
    sock.sendto(retry,(base,SIP_PORT))
    print(f'>>> Re-REGISTER retry CSeq={cseq} (new nonce)',flush=True)
   if time.monotonic()>=next_refresh:
    cseq+=1
    refresh=register_request(base,local,port,phone,cseq,cid,tag,challenge,a.mac)
    sock.sendto(refresh,(base,SIP_PORT))
    print(f'>>> Re-REGISTER CSeq={cseq}',flush=True)
    next_refresh=time.monotonic()+20
 except KeyboardInterrupt:pass
 finally:sock.close()"""

if old not in text:
    raise SystemExit('target block not found; file was not changed')

backup = TARGET.with_name(TARGET.name + '.bak_before_reregister')
if not backup.exists():
    shutil.copy2(TARGET, backup)

updated = text.replace(old, new, 1)
TARGET.write_text(updated, encoding='utf-8')
print('patched:', TARGET)
print('backup :', backup)
print('marker :', marker in updated)
