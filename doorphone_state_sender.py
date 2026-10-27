#!/usr/bin/env python3
import json,sys,re,xml.etree.ElementTree as ET
from urllib.request import Request,urlopen
from pathlib import Path

def parse(text):
 text=re.sub(r'^\s*<\?xml[^?]*\?>','',text.strip())
 root=ET.fromstring('<ROOT>'+text+'</ROOT>');out={}
 for section in root:
  values={}
  for child in section:
   values[child.tag]=(child.text or '').strip()
  out[section.tag]=values
 return out

path=Path(sys.argv[1]);url=sys.argv[2] if len(sys.argv)>2 else 'http://127.0.0.1:8787/api/doorphone/state'
body=json.dumps({'sections':parse(path.read_text(encoding='utf-8'))},ensure_ascii=False).encode()
req=Request(url,data=body,headers={'Content-Type':'application/json'},method='POST')
with urlopen(req,timeout=20) as r: print(r.read().decode())
