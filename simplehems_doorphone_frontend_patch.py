#!/usr/bin/env python3
from pathlib import Path
import re, shutil, sys

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2')
JS=ROOT/'frontend/src.jsx'; CSS=ROOT/'frontend/styles.css'
if not JS.exists(): raise SystemExit(f'not found: {JS}')
if not CSS.exists(): raise SystemExit(f'not found: {CSS}')
for p in (JS,CSS):
 b=p.with_name(p.name+'.bak_doorphone_state_ui')
 if not b.exists(): shutil.copy2(p,b)

s=JS.read_text(encoding='utf-8')
if 'doorphoneStateSections' not in s:
 m=re.search(r'(function DoorphonePage\(\)\s*\{.*?const \[error,setError\]\s*=\s*useState\(""\);)',s,re.S)
 if not m: raise SystemExit('DoorphonePage state anchor not found')
 add='''\n  const [doorphoneStateSections,setDoorphoneStateSections]=useState({});\n  const [doorphoneStateChanges,setDoorphoneStateChanges]=useState([]);\n  const [doorphoneStateError,setDoorphoneStateError]=useState("");\n  const loadDoorphoneState=async()=>{try{const r=await api("/api/doorphone/state");setDoorphoneStateSections(r.sections||{});setDoorphoneStateChanges(r.changes||[]);setDoorphoneStateError("");}catch(e){setDoorphoneStateError(e.message||String(e));}};\n  useEffect(()=>{loadDoorphoneState();const id=setInterval(loadDoorphoneState,5000);return()=>clearInterval(id);},[]);'''
 s=s[:m.end()]+add+s[m.end():]

if 'doorphoneStateMonitor' not in s:
 anchor=re.search(r'(\n\s*</div>\s*\n\s*\);\s*\n\}\s*\n\s*function CameraPage)',s)
 if not anchor: raise SystemExit('DoorphonePage end anchor not found')
 ui=r'''
      <section className="ratePanel doorphoneStateMonitor">
        <h3>状態モニター</h3>
        {doorphoneStateError&&<div className="error">{doorphoneStateError}</div>}
        {Object.keys(doorphoneStateSections).length===0?<p className="dim">状態データはまだありません</p>:
          <div className="doorphoneStateGrid">
            {Object.entries(doorphoneStateSections).map(([section,items])=><article className="doorphoneStateCard" key={section}>
              <h4>{section}</h4>
              <div className="doorphoneStateRows">
                {Object.entries(items||{}).map(([key,item])=><div className="doorphoneStateRow" key={key}>
                  <span className="doorphoneStateKey">{key}</span><strong className="doorphoneStateValue">{item?.value??""}</strong>
                </div>)}
              </div>
            </article>)}
          </div>}
      </section>
      <section className="ratePanel doorphoneStateChanges">
        <div className="doorphoneStateChangesHead"><h3>変更履歴</h3><button onClick={loadDoorphoneState}>更新</button></div>
        {doorphoneStateChanges.length===0?<p className="dim">変更履歴はまだありません</p>:
          <div className="doorphoneChangeList">
            {doorphoneStateChanges.map((x,i)=><div className="doorphoneChangeRow" key={`${x.event_time}-${x.section}-${x.key}-${i}`}>
              <small>{x.event_time}</small><span>{x.section}.{x.key}</span><strong>{x.old_value??""} → {x.new_value??""}</strong>
            </div>)}
          </div>}
      </section>'''
 pos=anchor.start(); s=s[:pos]+ui+s[pos:]
JS.write_text(s,encoding='utf-8')

c=CSS.read_text(encoding='utf-8')
marker='/* doorphone raw state monitor */'
if marker not in c:
 c+='''\n\n/* doorphone raw state monitor */\n.doorphoneStateGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}.doorphoneStateCard{border:1px solid rgba(128,128,128,.25);border-radius:12px;padding:12px;min-width:0}.doorphoneStateCard h4{margin:0 0 8px}.doorphoneStateRows{display:grid;gap:5px}.doorphoneStateRow{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid rgba(128,128,128,.13);padding:5px 0}.doorphoneStateKey{overflow-wrap:anywhere}.doorphoneStateValue{font-variant-numeric:tabular-nums;text-align:right}.doorphoneStateChangesHead{display:flex;align-items:center;justify-content:space-between;gap:12px}.doorphoneChangeList{display:grid;gap:7px}.doorphoneChangeRow{display:grid;grid-template-columns:minmax(120px,.8fr) minmax(180px,1.2fr) minmax(100px,.7fr);gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(128,128,128,.15)}@media(max-width:650px){.doorphoneStateGrid{grid-template-columns:1fr}.doorphoneChangeRow{grid-template-columns:1fr;gap:2px}.doorphoneChangeRow small{opacity:.7}}\n'''
CSS.write_text(c,encoding='utf-8')
print('patched:',JS);print('patched:',CSS);print('backup :',JS.with_name(JS.name+'.bak_doorphone_state_ui'));print('backup :',CSS.with_name(CSS.name+'.bak_doorphone_state_ui'))
