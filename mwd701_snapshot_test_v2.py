#!/usr/bin/env python3
"""One-shot VL-MWD701 JPEG CGI probe. Saves only a valid JPEG response."""
import argparse, base64, re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

def mac_bytes(value):
    s=re.sub(r'[^0-9A-Fa-f]','',value)
    if len(s)!=12: raise ValueError('MAC must contain 12 hex digits')
    return bytes.fromhex(s)
def interleave(a,b): return ''.join(f'{x:02x}{y:02x}' for x,y in zip(a,b))
def fetch(host,user,password,dst,timeout):
    url=f'http://{host}/SmpSnapshotJPEG?dst={dst}'
    token=base64.b64encode(f'{user}:{password}'.encode('ascii')).decode('ascii')
    req=Request(url,headers={'Authorization':'Basic '+token,'User-Agent':'Panasonic_Doorphone/2.1','Connection':'close'})
    try:
        with urlopen(req,timeout=timeout) as r:
            data=r.read(); return r.status,r.headers.get('Content-Type',''),data,url
    except HTTPError as e: return e.code,e.headers.get('Content-Type',''),e.read(),url

def main():
    p=argparse.ArgumentParser(); p.add_argument('--host',default='192.168.11.29');p.add_argument('--user',default='Smartphone1');p.add_argument('--phone-mac',required=True);p.add_argument('--base-mac',required=True);p.add_argument('--dst',action='append');p.add_argument('--output',default='mwd701_snapshot.jpg');p.add_argument('--timeout',type=float,default=5);a=p.parse_args()
    phone=mac_bytes(a.phone_mac);base=mac_bytes(a.base_mac)
    passwords=[('base-phone',interleave(base,phone)),('phone-base',interleave(phone,base))]
    destinations=a.dst or ['Door1','DOOR1','door1']
    for dst in destinations:
      for label,password in passwords:
        try: status,ctype,data,url=fetch(a.host,a.user,password,dst,a.timeout)
        except URLError as e:
          print(f'{dst} {label}: network error: {e.reason}');continue
        jpeg=data.startswith(b'\xff\xd8\xff') and data.rstrip().endswith(b'\xff\xd9')
        print(f'{dst} {label}: HTTP {status}, Content-Type={ctype!r}, bytes={len(data)}, jpeg={jpeg}')
        if status==200 and jpeg:
          Path(a.output).write_bytes(data);print('SAVED',a.output);print('URL',url);print('password-order',label);return
    raise SystemExit('No valid JPEG response. CGI may require an active monitoring session or a different dst/password order.')
if __name__=='__main__': main()
