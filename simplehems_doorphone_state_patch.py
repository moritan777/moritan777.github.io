#!/usr/bin/env python3
from pathlib import Path
import shutil, sys

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2')
SERVER=ROOT/'backend/server.py'
if not SERVER.exists(): raise SystemExit(f'not found: {SERVER}')
backup=SERVER.with_name('server.py.bak_doorphone_state')
if not backup.exists(): shutil.copy2(SERVER,backup)
s=SERVER.read_text(encoding='utf-8')

old='''def doorphone_db():\n c=sqlite3.connect(DPDB);c.row_factory=sqlite3.Row;c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_time TEXT NOT NULL,event_type TEXT NOT NULL,device_name TEXT,device_type TEXT,state TEXT,image_name TEXT,raw_payload TEXT)");c.commit();return c'''
new='''def doorphone_db():\n c=sqlite3.connect(DPDB);c.row_factory=sqlite3.Row\n c.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_time TEXT NOT NULL,event_type TEXT NOT NULL,device_name TEXT,device_type TEXT,state TEXT,image_name TEXT,raw_payload TEXT)")\n c.execute("CREATE TABLE IF NOT EXISTS current_state(section TEXT NOT NULL,key TEXT NOT NULL,value TEXT,updated_at TEXT NOT NULL,PRIMARY KEY(section,key))")\n c.execute("CREATE TABLE IF NOT EXISTS state_changes(id INTEGER PRIMARY KEY AUTOINCREMENT,event_time TEXT NOT NULL,section TEXT NOT NULL,key TEXT NOT NULL,old_value TEXT,new_value TEXT)")\n c.execute("CREATE INDEX IF NOT EXISTS ix_state_changes_time ON state_changes(event_time DESC)");c.commit();return c\n\ndef doorphone_state_apply(body):\n sections=body.get('sections') if isinstance(body,dict) else None\n if not isinstance(sections,dict):raise ValueError('sections must be an object')\n stamp=str(body.get('event_time') or datetime.now(timezone.utc).isoformat());c=doorphone_db();baseline=c.execute('SELECT COUNT(*) FROM current_state').fetchone()[0]==0;changes=[]\n for section,values in sections.items():\n  if not isinstance(values,dict):continue\n  for key,value in values.items():\n   section=str(section);key=str(key);value='' if value is None else str(value);old=c.execute('SELECT value FROM current_state WHERE section=? AND key=?',(section,key)).fetchone()\n   if old is not None and old['value']!=value:\n    c.execute('INSERT INTO state_changes(event_time,section,key,old_value,new_value) VALUES(?,?,?,?,?)',(stamp,section,key,old['value'],value));changes.append({'event_time':stamp,'section':section,'key':key,'old_value':old['value'],'new_value':value})\n   c.execute('INSERT INTO current_state(section,key,value,updated_at) VALUES(?,?,?,?) ON CONFLICT(section,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(section,key,value,stamp))\n c.commit();c.close();return {'ok':True,'baseline':baseline,'changes':changes,'changed':len(changes)}\n\ndef doorphone_state_data():\n c=doorphone_db();rows=c.execute('SELECT section,key,value,updated_at FROM current_state ORDER BY section,key').fetchall();changes=c.execute('SELECT event_time,section,key,old_value,new_value FROM state_changes ORDER BY id DESC LIMIT 500').fetchall();c.close();sections={}\n for r in rows:sections.setdefault(r['section'],{})[r['key']]={'value':r['value'],'updated_at':r['updated_at']}\n return {'sections':sections,'changes':[dict(x) for x in changes]}'''
if old not in s: raise SystemExit('doorphone_db anchor not found; no changes made')
s=s.replace(old,new,1)

old="if u.path=='/api/doorphone':return self.send_data(doorphone_data())"
new="if u.path=='/api/doorphone':return self.send_data(doorphone_data())\n   if u.path=='/api/doorphone/state':return self.send_data(doorphone_state_data())"
if old not in s: raise SystemExit('GET anchor not found; no changes written')
s=s.replace(old,new,1)
old="if self.path=='/api/doorphone/event':return self.send_data(doorphone_add(body))"
new="if self.path=='/api/doorphone/event':return self.send_data(doorphone_add(body))\n   if self.path=='/api/doorphone/state':return self.send_data(doorphone_state_apply(body))"
if old not in s: raise SystemExit('POST anchor not found; no changes written')
s=s.replace(old,new,1)
SERVER.write_text(s,encoding='utf-8')
print('patched:',SERVER)
print('backup :',backup)
