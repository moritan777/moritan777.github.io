#!/usr/bin/env python3
"""VL-MWD701 pairing, Digest REGISTER, NOTIFY decrypt and SimpleHEMS state bridge."""
import argparse, base64, hashlib, json, random, re, socket, time, uuid
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
DISCOVERY_PORT=50000; SIP_PORT=5060; UA='Panasonic_Doorphone/2.1'
def norm_mac(x):
 v=re.sub(r'[^0-9A-Fa-f]','',x).lower()
 if len(v)!=12: raise ValueError('MAC must contain exactly 12 hexadecimal digits')
 return v
def password_for(x): return hashlib.md5(norm_mac(x).encode()).hexdigest().upper()
def md5(x): return hashlib.md5(x.encode()).hexdigest()
def local_ip_for(remote):
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
 try:s.connect((remote,SIP_PORT));return s.getsockname()[0]
 finally:s.close()
def parse_message(raw):
 head,sep,body=raw.partition(b'\r\n\r\n'); text=head.decode('utf-8','replace'); lines=text.split('\r\n'); h={}
 for line in lines[1:]:
  if ':' in line:
   k,v=line.split(':',1);h.setdefault(k.lower().strip(),[]).append(v.strip())
 return lines[0] if lines else '',h,body,raw.decode('utf-8','replace')
def discover(timeout=5,target='255.255.255.255'):
 tcp=socket.socket();tcp.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);tcp.bind(('0.0.0.0',0));tcp.listen(4);tcp.settimeout(timeout)
 port=tcp.getsockname()[1]; udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
 payload=f'pnvi,{port},00:00:00:00:00:00'.encode();udp.sendto(payload,(target,DISCOVERY_PORT));print('>>> discovery',payload.decode(),flush=True);found=[];end=time.time()+timeout
 while time.time()<end:
  try:conn,addr=tcp.accept()
  except socket.timeout:break
  with conn:
   raw=conn.recv(2048).rstrip(b'\0').decode('utf-8','replace');parts=[x.strip() for x in raw.split(',')];found.append({'ip':parts[0] if parts else addr[0],'raw':raw});print('<<< discovery',raw,flush=True)
 tcp.close();udp.close();return found
def pair_request(base,local,port,mac):
 body='00<?xml version="1.0" encoding="UTF-8"?>'+f'<REGISTER><MAC>{norm_mac(mac)}</MAC></REGISTER>'
 lines=[f'MESSAGE sip:Server@{base}> SIP/2.0',f'Via: SIP/2.0/UDP {local}:{port};branch=z9hG4bK{uuid.uuid4().hex[:8]}','Max-Forwards: 70',f'To: <sip:Server@{base}>>',f'From: <sip:Client@{base}>;tag={random.randint(100000000,1999999999)}',f'Call-ID: {uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:16]}@[{local}]','CSeq: 1 MESSAGE','Allow: BYE,NOTIFY','Content-Type: application/text',f'User-Agent: {UA}',f'Content-Length: {len(body.encode())}','','']
 return ('\r\n'.join(lines)+body).encode()
def extract_phone_id(text):
 for p in [r'PSN-Notify-PSnum\s*:\s*([A-Za-z0-9_-]+)',r'\b(Smartphone[1-4])\b']:
  m=re.search(p,text,re.I)
  if m:return m.group(1)
def register_request(base,local,port,user,cseq,call_id,tag,challenge=None,mac=None):
 uri=f'sip:{base};transport=udp';lines=[f'REGISTER {uri} SIP/2.0',f'Via: SIP/2.0/UDP {local}:{port};branch=z9hG4bK{uuid.uuid4().hex[:8]};rport','Max-Forwards: 70',f'To: <sip:{user}@{base}>',f'From: <sip:{user}@{base}>;tag={tag}',f'Call-ID: {call_id}',f'CSeq: {cseq} REGISTER',f'Contact: <sip:{user}@{local}:{port}>','Expires: 30',f'User-Agent: {UA}']
 if challenge:
  realm=re.search(r'realm="([^"]+)"',challenge,re.I).group(1);nonce=re.search(r'nonce="([^"]+)"',challenge,re.I).group(1);alg=(re.search(r'algorithm\s*=\s*([^,\s]+)',challenge,re.I) or [None,'MD5'])[1];q=(re.search(r'qop="?([^",]+)',challenge,re.I));qop=q.group(1).strip() if q else None
  pw=password_for(mac);ha1=md5(f'{user}:{realm}:{pw}');ha2=md5(f'REGISTER:{uri}');fields=[f'username="{user}"',f'realm="{realm}"',f'nonce="{nonce}"',f'uri="{uri}"']
  if qop:
   nc='00000001';cn=uuid.uuid4().hex[:16];response=md5(f'{ha1}:{nonce}:{nc}:{cn}:{qop}:{ha2}');fields += [f'response="{response}"',f'algorithm={alg}',f'qop={qop}',f'nc={nc}',f'cnonce="{cn}"']
  else:fields += [f'response="{md5(f"{ha1}:{nonce}:{ha2}")}"',f'algorithm={alg}']
  lines.append('Authorization: Digest '+', '.join(fields))
 lines += ['Content-Length: 0','',''];return '\r\n'.join(lines).encode()
def response_for_request(h):
 to=h.get('to',[''])[0]
 if 'tag=' not in to:to+=';tag='+uuid.uuid4().hex[:8]
 lines=['SIP/2.0 200 OK',f"Via: {h.get('via',[''])[0]}",f'To: {to}',f"From: {h.get('from',[''])[0]}",f"Call-ID: {h.get('call-id',[''])[0]}",f"CSeq: {h.get('cseq',[''])[0]}",'Content-Length: 0','',''];return '\r\n'.join(lines).encode()
def decrypt_notify(body,password):
 p=b''.join(body.split()).decode('ascii')
 if not p.startswith('01'):raise ValueError('unsupported NOTIFY envelope')
 salt=bytes.fromhex(p[2:18]);iv=bytes.fromhex(p[18:50]);expected=int(p[50:54],16);ct=base64.b64decode(p[54:],validate=True);key=hashlib.pbkdf2_hmac('sha1',password.encode(),salt,1000,dklen=16);d=Cipher(algorithms.AES(key),modes.CBC(iv)).decryptor();padded=d.update(ct)+d.finalize();u=padding.PKCS7(128).unpadder();plain=u.update(padded)+u.finalize()
 if len(plain)!=expected:raise ValueError(f'plaintext length {len(plain)} != {expected}')
 return plain.decode('utf-8')
def xml_sections(text):
 text=re.sub(r'^\s*<\?xml[^?]*\?>','',text.strip());root=ET.fromstring('<ROOT>'+text+'</ROOT>');return {s.tag:{c.tag:(c.text or '').strip() for c in s} for s in root}
def post_state(url,sections):
 req=Request(url,data=json.dumps({'sections':sections},ensure_ascii=False).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urlopen(req,timeout=20) as r:return r.read().decode()
def recv_until(sock,seconds,password,api,phone_id=None):
 end=time.time()+seconds;packets=[]
 while time.time()<end:
  sock.settimeout(max(.1,end-time.time()))
  try:raw,addr=sock.recvfrom(65535)
  except socket.timeout:break
  start,h,body,text=parse_message(raw);print('\n<<<',addr,'\n',text,flush=True);packets.append((start,h,body,text,addr))
  if start.startswith('NOTIFY '):
   sock.sendto(response_for_request(h),addr);print('>>> 200 OK (NOTIFY)',flush=True)
   try:print('>>> state',post_state(api,xml_sections(decrypt_notify(body,password))),flush=True)
   except Exception as e:print('>>> NOTIFY decode/state ERROR:',repr(e),flush=True)
  phone_id=phone_id or extract_phone_id(text)
 return packets,phone_id
def main():
 p=argparse.ArgumentParser();p.add_argument('--ip');p.add_argument('--mac',required=True);p.add_argument('--phone-id');p.add_argument('--local-ip');p.add_argument('--port',type=int,default=0);p.add_argument('--timeout',type=float,default=8);p.add_argument('--api',default='http://127.0.0.1:8787/api/doorphone/state');a=p.parse_args();base=a.ip
 if not base:
  f=discover(a.timeout)
  if not f:raise SystemExit('Parent unit was not discovered')
  base=f[0]['ip']
 local=a.local_ip or local_ip_for(base);sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind((local,a.port));port=sock.getsockname()[1];pw=password_for(a.mac);print(f'local={local}:{port} base={base}:{SIP_PORT} password={pw}',flush=True);phone=a.phone_id
 if not phone:
  req=pair_request(base,local,port,a.mac);print('\n=== PAIR MESSAGE ===\n'+req.decode(),flush=True);sock.sendto(req,(base,SIP_PORT));packets,phone=recv_until(sock,a.timeout,pw,a.api)
  if any('486 Busy Here' in x[0] for x in packets):raise SystemExit('Parent unit returned 486 Busy Here')
  if not phone:raise SystemExit('PhoneID was not received')
 print('PhoneID =',phone,flush=True);cid=uuid.uuid4().hex+'@'+local;tag='reg'+uuid.uuid4().hex[:8];r1=register_request(base,local,port,phone,1,cid,tag);sock.sendto(r1,(base,SIP_PORT));packets,_=recv_until(sock,a.timeout,pw,a.api,phone);challenge=next((h.get('www-authenticate',[None])[0] for st,h,*_ in packets if st.startswith('SIP/2.0 401')),None)
 if not challenge:raise SystemExit('401 Digest challenge was not received')
 r2=register_request(base,local,port,phone,2,cid,tag,challenge,a.mac);sock.sendto(r2,(base,SIP_PORT));packets,_=recv_until(sock,a.timeout,pw,a.api,phone)
 if not any(st.startswith('SIP/2.0 200') for st,*_ in packets):raise SystemExit('Authenticated REGISTER did not receive 200 OK')
 print('REGISTER successful. Waiting for NOTIFY. Ctrl+C to stop.',flush=True)
 try:
  while True:recv_until(sock,60,pw,a.api,phone)
 except KeyboardInterrupt:pass
 finally:sock.close()
if __name__=='__main__':main()
