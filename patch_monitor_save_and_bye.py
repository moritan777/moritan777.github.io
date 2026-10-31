#!/usr/bin/env python3
from pathlib import Path
import shutil,sys
p=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2/tools/mwd701_monitor_test_v2.py')
if not p.exists():raise SystemExit(f'not found: {p}')
s=p.read_text(encoding='utf-8')
if 'SimpleHEMS image event saved' in s:print('already patched');raise SystemExit(0)
b=p.with_name(p.name+'.bak_before_save_bye')
if not b.exists():shutil.copy2(p,b)
# imports
s=s.replace('import argparse,base64,hashlib,re,socket,time,uuid','import argparse,base64,hashlib,json,re,socket,time,uuid\nfrom datetime import datetime,timezone')
s=s.replace('from urllib.request import Request,urlopen','from urllib.request import Request,urlopen')
# helper before main
anchor='def main():\n'
helper='''def post_image_event(url,path):\n data=Path(path).read_bytes()\n body={"event_time":datetime.now(timezone.utc).isoformat(),"event_type":"snapshot","device_name":"Door1","device_type":"doorphone","state":"captured","image_base64":base64.b64encode(data).decode("ascii"),"raw_payload":{"source":"SmpSnapshotJPEG","width":640,"height":480}}\n req=Request(url,data=json.dumps(body,ensure_ascii=False).encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")\n with urlopen(req,timeout=20) as r:return r.read().decode("utf-8","replace")\ndef send_bye(sip,host,local,port,user,tag,cid,to):\n branch="z9hG4bK"+uuid.uuid4().hex[:8]\n bye="\\r\\n".join([f"BYE sip:Server@{host}:5060 SIP/2.0",f"Via: SIP/2.0/UDP {local}:{port};branch={branch}","Max-Forwards: 70",f"To: {to}",f"From: <sip:{user}@{host}>;tag={tag}",f"Call-ID: {cid}","CSeq: 2 BYE",f"Contact: <sip:{user}@{local}:{port}>","Content-Length: 0","",""])\n sip.sendto(bye.encode(),(host,5060));print(">>> BYE",flush=True)\n r=recv_for(sip,5,cid,"BYE",final_only=True)\n print("BYE RESULT",r[0] if r else "timeout",flush=True)\n'''
if anchor not in s:raise SystemExit('main anchor not found')
s=s.replace(anchor,helper+anchor,1)
# arguments
old="p=argparse.ArgumentParser();a=p.parse_args();"
if old in s:
 s=s.replace(old,"p=argparse.ArgumentParser();p.add_argument('--api-event',default='http://127.0.0.1:8787/api/doorphone/event');a=p.parse_args();",1)
else:
 old="p=argparse.ArgumentParser();p.add_argument('--host',default='192.168.11.29');p.add_argument('--user',default='Smartphone1');p.add_argument('--phone-mac',required=True);p.add_argument('--base-mac',required=True);p.add_argument('--output',default='mwd701_monitor.jpg');x=p.parse_args()"
 new="p=argparse.ArgumentParser();p.add_argument('--host',default='192.168.11.29');p.add_argument('--user',default='Smartphone1');p.add_argument('--phone-mac',required=True);p.add_argument('--base-mac',required=True);p.add_argument('--output',default='mwd701_monitor.jpg');p.add_argument('--api-event',default='http://127.0.0.1:8787/api/doorphone/event');x=p.parse_args()"
 if old not in s:raise SystemExit('argument anchor not found')
 s=s.replace(old,new,1)
# replace result/close tail
old="print('RESULT',x.output if ok else 'no JPEG')\n sip.close();audio.close()"
new="""print('RESULT',x.output if ok else 'no JPEG')
 try:
  if ok:
   print('SimpleHEMS image event saved',post_image_event(x.api_event,x.output),flush=True)
 finally:
  send_bye(sip,x.host,local,port,x.user,tag,cid,to)
  sip.close();audio.close()"""
if old not in s:raise SystemExit('result tail not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('patched:',p);print('backup:',b)
