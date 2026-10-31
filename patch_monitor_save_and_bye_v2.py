#!/usr/bin/env python3
from pathlib import Path
import shutil,sys
p=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2/tools/mwd701_monitor_test_v2.py')
if not p.exists():raise SystemExit(f'not found: {p}')
s=p.read_text(encoding='utf-8')
if 'SimpleHEMS image event saved' in s:print('already patched');raise SystemExit(0)
b=p.with_name(p.name+'.bak_before_save_bye_v2')
if not b.exists():shutil.copy2(p,b)
s=s.replace('import argparse,base64,hashlib,re,socket,time,uuid','import argparse,base64,hashlib,json,re,socket,time,uuid\nfrom datetime import datetime,timezone',1)
main='def main():\n'
helper='''def post_image_event(url,path):
 data=Path(path).read_bytes()
 body={"event_time":datetime.now(timezone.utc).isoformat(),"event_type":"snapshot","device_name":"Door1","device_type":"doorphone","state":"captured","image_base64":base64.b64encode(data).decode("ascii"),"raw_payload":{"source":"SmpSnapshotJPEG","width":640,"height":480}}
 req=Request(url,data=json.dumps(body,ensure_ascii=False).encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
 with urlopen(req,timeout=20) as r:return r.read().decode("utf-8","replace")
def send_bye(sip,host,local,port,user,tag,cid,to):
 branch="z9hG4bK"+uuid.uuid4().hex[:8]
 bye="\\r\\n".join([f"BYE sip:Server@{host}:5060 SIP/2.0",f"Via: SIP/2.0/UDP {local}:{port};branch={branch}","Max-Forwards: 70",f"To: {to}",f"From: <sip:{user}@{host}>;tag={tag}",f"Call-ID: {cid}","CSeq: 2 BYE",f"Contact: <sip:{user}@{local}:{port}>","Content-Length: 0","",""])
 sip.sendto(bye.encode(),(host,5060));print(">>> BYE",flush=True)
 r=recv_for(sip,5,cid,"BYE",final_only=True)
 print("BYE RESULT",r[0] if r else "timeout",flush=True)
'''
if main not in s:raise SystemExit('main anchor not found')
s=s.replace(main,helper+main,1)
arg="a.add_argument('--output',default='mwd701_monitor.jpg');x=a.parse_args();local=local_ip(x.host)"
rep="a.add_argument('--output',default='mwd701_monitor.jpg');a.add_argument('--api-event',default='http://127.0.0.1:8787/api/doorphone/event');x=a.parse_args();local=local_ip(x.host)"
if arg not in s:raise SystemExit('argument anchor not found; file was not changed')
s=s.replace(arg,rep,1)
tail="print('RESULT',x.output if ok else 'no JPEG')\n sip.close();audio.close()"
newtail="""print('RESULT',x.output if ok else 'no JPEG')
 try:
  if ok:print('SimpleHEMS image event saved',post_image_event(x.api_event,x.output),flush=True)
 finally:
  send_bye(sip,x.host,local,port,x.user,tag,cid,to)
  sip.close();audio.close()"""
if tail not in s:raise SystemExit('result tail not found; file was not changed')
s=s.replace(tail,newtail,1)
p.write_text(s,encoding='utf-8')
print('patched:',p);print('backup:',b);print('markers:', 'SimpleHEMS image event saved' in s, '>>> BYE' in s)
