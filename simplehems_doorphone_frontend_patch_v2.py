#!/usr/bin/env python3
from pathlib import Path
import shutil, sys
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2')
JS=ROOT/'frontend/src.jsx'; CSS=ROOT/'frontend/style.css'
if not JS.exists(): raise SystemExit(f'not found: {JS}')
if not CSS.exists(): raise SystemExit(f'not found: {CSS}')
for f in (JS,CSS):
 b=f.with_name(f.name+'.bak_doorphone_state_ui_v2')
 if not b.exists(): shutil.copy2(f,b)
s=JS.read_text(encoding='utf-8')
start=s.find('function DoorphonePage()'); end=s.find('function CameraPage()',start)
if start<0 or end<0: raise SystemExit('DoorphonePage/CameraPage boundary not found')
seg=s[start:end]
if 'doorphoneStateSections' not in seg:
 anchors=['const [error,setError] = useState("");','const [error,setError]=useState("");']
 anchor=next((x for x in anchors if x in seg),None)
 if not anchor: raise SystemExit('error state anchor not found')
 state='''\n  const [doorphoneStateSections,setDoorphoneStateSections]=useState({});\n  const [doorphoneStateChanges,setDoorphoneStateChanges]=useState([]);\n  const [doorphoneStateError,setDoorphoneStateError]=useState("");\n  const loadDoorphoneState=async()=>{try{const r=await api("/api/doorphone/state");setDoorphoneStateSections(r.sections||{});setDoorphoneStateChanges(r.changes||[]);setDoorphoneStateError("");}catch(e){setDoorphoneStateError(e.message||String(e));}};\n  useEffect(()=>{loadDoorphoneState();const id=setInterval(loadDoorphoneState,5000);return()=>clearInterval(id);},[]);'''
 seg=seg.replace(anchor,anchor+state,1)
if 'doorphoneStateMonitor' not in seg:
 ui='''\n      <section className="ratePanel doorphoneStateMonitor">\n        <div className="doorphoneStateHead"><div><div className="eyebrow">RAW STATE</div><h3>状態モニター</h3></div><button onClick={loadDoorphoneState}>更新</button></div>\n        {doorphoneStateError&&<div className="error">{doorphoneStateError}</div>}\n        {Object.keys(doorphoneStateSections).length===0?<p className="dim">状態データはまだありません</p>:<div className="doorphoneStateGrid">{Object.entries(doorphoneStateSections).map(([section,items])=><article className="doorphoneStateCard" key={section}><h4>{section}</h4><div className="doorphoneStateRows">{Object.entries(items||{}).map(([key,item])=><div className="doorphoneStateRow" key={key}><span>{key}</span><strong>{item?.value??""}</strong></div>)}</div></article>)}</div>}\n      </section>\n      <section className="ratePanel doorphoneStateChanges">\n        <div className="eyebrow">CHANGE LOG</div><h3>変更履歴</h3>\n        {doorphoneStateChanges.length===0?<p className="dim">変更履歴はまだありません</p>:<div className="doorphoneChangeList">{doorphoneStateChanges.map((x,i)=><div className="doorphoneChangeRow" key={String(i)+String(x.event_time)+String(x.section)+String(x.key)}><small>{x.event_time}</small><span>{x.section}.{x.key}</span><strong>{x.old_value??""} -&gt; {x.new_value??""}</strong></div>)}</div>}\n      </section>\n'''
 marker='    </div>\n  );\n}\n\n'
 pos=seg.rfind(marker)
 if pos<0: raise SystemExit('DoorphonePage closing anchor not found')
 seg=seg[:pos]+ui+seg[pos:]
s=s[:start]+seg+s[end:]; JS.write_text(s,encoding='utf-8')
c=CSS.read_text(encoding='utf-8'); mark='/* doorphone raw state monitor v2 */'
if mark not in c:
 c+='''\n\n/* doorphone raw state monitor v2 */\n.doorphoneStateHead{display:flex;align-items:center;justify-content:space-between;gap:12px}.doorphoneStateGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:12px}.doorphoneStateCard{border:1px solid rgba(120,170,210,.2);background:rgba(5,20,35,.25);border-radius:12px;padding:12px;min-width:0}.doorphoneStateCard h4{margin:0 0 8px;color:#78c8ff}.doorphoneStateRows{display:grid;gap:4px}.doorphoneStateRow{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid rgba(128,160,190,.12)}.doorphoneStateRow span{overflow-wrap:anywhere}.doorphoneStateRow strong{font-variant-numeric:tabular-nums;text-align:right}.doorphoneChangeList{display:grid;gap:6px;margin-top:10px}.doorphoneChangeRow{display:grid;grid-template-columns:minmax(145px,.8fr) minmax(180px,1.2fr) minmax(100px,.7fr);gap:10px;padding:7px 0;border-bottom:1px solid rgba(128,160,190,.15)}@media(max-width:650px){.doorphoneStateGrid{grid-template-columns:1fr}.doorphoneChangeRow{grid-template-columns:1fr;gap:2px}.doorphoneChangeRow small{opacity:.7}}\n'''
CSS.write_text(c,encoding='utf-8')
text=JS.read_text(encoding='utf-8')
print('patched:',JS); print('patched:',CSS); print('state marker:', 'doorphoneStateSections' in text); print('ui marker:', '状態モニター' in text)
