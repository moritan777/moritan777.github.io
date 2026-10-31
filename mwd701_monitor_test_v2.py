#!/usr/bin/env python3
import argparse,base64,hashlib,re,socket,time,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def md5(s):return hashlib.md5(s.encode()).hexdigest()
def mac12(s):return re.sub(r'[^0-9a-fA-F]','',s).lower()
def password_for(s):return hashlib.md5(mac12(s).encode()).hexdigest().upper()
def local_ip(host):
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect((host,5060));v=s.getsockname()[0];s.close();return v
def parse(b):
 text=b.decode('utf-8','replace');head,_,body=text.partition('\r\n\r\n');lines=head.split('\r\n');h={}
 for x in lines[1:]:
  if ':' in x:k,v=x.split(':',1);h[k.lower()]=v.strip()
 return lines[0],h,body,text
def recv_for(s,seconds,callid=None,cseq_method=None,final_only=False):
 end=time.time()+seconds
 while time.time()<end:
  s.settimeout(max(.1,end-time.time()))
  try:b,a=s.recvfrom(65535)
  except socket.timeout:return None
  st,h,body,text=parse(b);print('\n<<<',a,'\n'+text,flush=True)
  if st.startswith('NOTIFY '):s.sendto(ok_for(h),a);continue
  if callid and h.get('call-id')!=callid:continue
  if cseq_method and not h.get('cseq','').endswith(cseq_method):continue
  if final_only and re.match(r'^SIP/2\.0 1\d\d(?: |$)',st):
   print('... provisional response; waiting for final response',flush=True)
   continue
  return st,h,body
def ok_for(h):
 to=h.get('to','');to=to if 'tag=' in to else to+';tag='+uuid.uuid4().hex[:8]
 return ('\r\n'.join(['SIP/2.0 200 OK','Via: '+h.get('via',''),'To: '+to,'From: '+h.get('from',''),'Call-ID: '+h.get('call-id',''),'CSeq: '+h.get('cseq',''),'Content-Length: 0','',''])).encode()
def register(s,base,local,port,user,mac):
 uri=f'sip:{base};transport=udp';cid=uuid.uuid4().hex+'@'+local;tag='reg'+uuid.uuid4().hex[:8]
 def req(cseq,auth=None):
  L=[f'REGISTER {uri} SIP/2.0',f'Via: SIP/2.0/UDP {local}:{port};branch=z9hG4bK{uuid.uuid4().hex[:8]};rport','Max-Forwards: 70',f'To: <sip:{user}@{base}>',f'From: <sip:{user}@{base}>;tag={tag}',f'Call-ID: {cid}',f'CSeq: {cseq} REGISTER',f'Contact: <sip:{user}@{local}:{port}>','Expires: 30','Allow: BYE,NOTIFY','User-Agent: Panasonic_ドアホン/2.1']
  if auth:L.append('Authorization: '+auth)
  L+=['Content-Length: 0','',''];return '\r\n'.join(L).encode()
 s.sendto(req(1),(base,5060));r=recv_for(s,5,cid,'REGISTER')
 if not r or not r[0].startswith('SIP/2.0 401'):raise RuntimeError('REGISTER challenge missing')
 wa=r[1]['www-authenticate'];realm=re.search(r'realm="([^"]+)"',wa).group(1);nonce=re.search(r'nonce="([^"]+)"',wa).group(1);pw=password_for(mac);resp=md5(f'{md5(f"{user}:{realm}:{pw}")}:{nonce}:{md5(f"REGISTER:{uri}")}')
 auth=f'Digest realm="{realm}", nonce="{nonce}", algorithm=MD5, uri="{uri}", username="{user}", response="{resp}"'
 s.sendto(req(2,auth),(base,5060));r=recv_for(s,5,cid,'REGISTER')
 if not r or not r[0].startswith('SIP/2.0 200'):raise RuntimeError('REGISTER failed')
def cgi_password(phone,base):
 p=bytes.fromhex(mac12(phone));b=bytes.fromhex(mac12(base));return ''.join(f'{x:02x}{y:02x}' for x,y in zip(b,p))
def fetch(host,user,password,out):
 token=base64.b64encode(f'{user}:{password}'.encode()).decode();req=Request(f'http://{host}/SmpSnapshotJPEG?dst=Door1',headers={'Authorization':'Basic '+token,'User-Agent':'Panasonic_Doorphone/2.1','Connection':'close'})
 try:
  with urlopen(req,timeout=3) as r:data=r.read();code=r.status
 except HTTPError as e:data=e.read();code=e.code
 ok=code==200 and data.startswith(b'\xff\xd8\xff');print('CGI',code,len(data),'jpeg',ok,flush=True)
 if ok:Path(out).write_bytes(data)
 return ok
def main():
 a=argparse.ArgumentParser();a.add_argument('--host',default='192.168.11.29');a.add_argument('--user',default='Smartphone1');a.add_argument('--phone-mac',required=True);a.add_argument('--base-mac',required=True);a.add_argument('--output',default='mwd701_monitor.jpg');x=a.parse_args();local=local_ip(x.host)
 sip=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sip.bind((local,0));port=sip.getsockname()[1];audio=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);audio.bind((local,0));audio_port=audio.getsockname()[1]
 print('local',local,'sip',port,'audio',audio_port);register(sip,x.host,local,port,x.user,x.phone_mac)
 cid=uuid.uuid4().hex+'@['+local+']';tag=str(int(time.time()*1000)%2000000000);branch='z9hG4bK'+uuid.uuid4().hex[:8];sid=int(time.time());sdp='\r\n'.join(['v=0',f'o=- {sid} {sid+1} IN IP4 {local}','s=Monitor Door1',f'c=IN IP4 {local}','t=0 0',f'm=audio {audio_port} RTP/AVP 0','a=rtpmap:0 PCMU/8000','a=sendrecv',''])
 L=[f'INVITE sip:Server@{x.host} SIP/2.0',f'Via: SIP/2.0/UDP {local}:{port};branch={branch}','Max-Forwards: 70',f'To: <sip:Server@{x.host}>',f'From: <sip:{x.user}@{x.host}>;tag={tag}',f'Call-ID: {cid}','CSeq: 1 INVITE',f'Contact: <sip:{x.user}@{local}:{port}>','Supported: timer','Session-Expires: 20;refresher=uas','Allow: BYE,NOTIFY','User-Agent: Panasonic_ドアホン/2.1','Content-Type: application/sdp',f'Content-Length: {len(sdp.encode())}','','']
 invite=('\r\n'.join(L)+sdp).encode();print('\n>>> INVITE\n'+invite.decode());sip.sendto(invite,(x.host,5060));r=recv_for(sip,12,cid,'INVITE',final_only=True)
 if not r or not r[0].startswith('SIP/2.0 200'):raise SystemExit('INVITE did not receive 200 OK')
 to=r[1]['to'];ack='\r\n'.join([f'ACK sip:Server@{x.host}:5060 SIP/2.0',f'Via: SIP/2.0/UDP {local}:{port};branch={branch}','Max-Forwards: 70',f'To: {to}',f'From: <sip:{x.user}@{x.host}>;tag={tag}',f'Call-ID: {cid}','CSeq: 1 ACK','Content-Length: 0','','']);sip.sendto(ack.encode(),(x.host,5060));print('>>> ACK')
 pw=cgi_password(x.phone_mac,x.base_mac);ok=False
 for _ in range(20):
  if fetch(x.host,x.user,pw,x.output):ok=True;break
  time.sleep(.25)
 print('RESULT',x.output if ok else 'no JPEG')
 sip.close();audio.close()
if __name__=='__main__':main()
