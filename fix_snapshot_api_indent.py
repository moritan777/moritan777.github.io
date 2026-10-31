#!/usr/bin/env python3
from pathlib import Path
import sys
p=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2/backend/server.py')
if not p.exists(): raise SystemExit(f'not found: {p}')
s=p.read_text(encoding='utf-8')
lines=s.splitlines()
found=False
for i,line in enumerate(lines):
    if "if self.path=='/api/doorphone/snapshot':" in line:
        base=len(line)-len(line.lstrip())
        if i+2>=len(lines): raise SystemExit('snapshot route is truncated')
        if 'snapshot.request' not in lines[i+1] or 'queued' not in lines[i+2]:
            raise SystemExit('snapshot route body does not match expected inserted code')
        lines[i+1]=' '*(base+4)+lines[i+1].lstrip()
        lines[i+2]=' '*(base+4)+lines[i+2].lstrip()
        found=True
        break
if not found: raise SystemExit('snapshot route not found')
p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('fixed:',p)
print('route:')
for x in lines[i:i+4]: print(repr(x))
