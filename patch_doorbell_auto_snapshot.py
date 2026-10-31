#!/usr/bin/env python3
from pathlib import Path
import shutil, subprocess, sys
p=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2/backend/server.py')
if not p.exists(): raise SystemExit(f'not found: {p}')
s=p.read_text(encoding='utf-8')
marker='doorbell auto snapshot trigger'
if marker in s:
 print('already patched:',p); raise SystemExit(0)
start=s.find('def doorphone_state_apply(')
if start<0: raise SystemExit('doorphone_state_apply not found')
end=s.find('\ndef ',start+4)
if end<0:end=len(s)
seg=s[start:end]
anchor="c.commit();c.close();return {'ok':True,'baseline':baseline,'changes':changes,'changed':len(changes)}"
pos=seg.find(anchor)
if pos<0: raise SystemExit('state apply return anchor not found; no changes made')
line_start=seg.rfind('\n',0,pos)+1
indent=seg[line_start:pos]
if indent.strip(): raise SystemExit('could not determine indentation; no changes made')
insert=(indent+"# doorbell auto snapshot trigger\n"+
        indent+"ring_started=any(x.get('section')=='CALL_INFO' and x.get('key')=='MAIN_RING' and x.get('old_value')=='0' and x.get('new_value')=='1' for x in changes)\n"+
        indent+"main_call=str((sections.get('CALL_INFO') or {}).get('MAIN_CALL',''))\n"+
        indent+"if ring_started and main_call=='Door1':\n"+
        indent+" try:\n"+
        indent+"  open('/run/simplehems-doorphone/snapshot.request','w').write(stamp)\n"+
        indent+" except Exception:logging.exception('doorbell auto snapshot request failed')\n")
seg=seg[:line_start]+insert+seg[line_start:]
updated=s[:start]+seg+s[end:]
backup=p.with_name(p.name+'.bak_before_doorbell_auto_snapshot')
if not backup.exists():shutil.copy2(p,backup)
p.write_text(updated,encoding='utf-8')
py='/home/hems/simplehems-server-v2/.venv/bin/python'
r=subprocess.run([py,'-m','py_compile',str(p)],capture_output=True,text=True)
if r.returncode:
 shutil.copy2(backup,p)
 print(r.stderr,end='')
 raise SystemExit('compile failed; original restored')
print('patched:',p)
print('backup :',backup)
print('compile: OK')
print('condition: CALL_INFO.MAIN_RING 0->1 and MAIN_CALL=Door1')
