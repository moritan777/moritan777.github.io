#!/usr/bin/env python3
from pathlib import Path
import shutil, sys

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/home/hems/simplehems-server-v2')
JS=ROOT/'frontend/src.jsx'
CSS=ROOT/'frontend/style.css'
if not JS.exists(): raise SystemExit(f'not found: {JS}')
if not CSS.exists(): raise SystemExit(f'not found: {CSS}')

js_backup=JS.with_name('src.jsx.bak_doorphone_state_ui_v3')
css_backup=CSS.with_name('style.css.bak_doorphone_state_ui_v3')
if not js_backup.exists(): shutil.copy2(JS,js_backup)
if not css_backup.exists(): shutil.copy2(CSS,css_backup)

s=JS.read_text(encoding='utf-8')
start=s.find('function DoorphonePage() {')
end=s.find('\nfunction CameraPage() {',start)
if start<0 or end<0: raise SystemExit('DoorphonePage boundary not found')
seg=s[start:end]

if 'doorphoneStateSections' not in seg:
    insert_at=seg.find('\n',seg.find('function DoorphonePage() {'))+1
    state='''  const [doorphoneStateSections, setDoorphoneStateSections] = useState({});
  const [doorphoneStateChanges, setDoorphoneStateChanges] = useState([]);
  const [doorphoneStateError, setDoorphoneStateError] = useState("");
  const loadDoorphoneState = async () => {
    try {
      const r = await api("/api/doorphone/state");
      setDoorphoneStateSections(r.sections || {});
      setDoorphoneStateChanges(r.changes || []);
      setDoorphoneStateError("");
    } catch (e) { setDoorphoneStateError(e.message || String(e)); }
  };
  useEffect(() => { loadDoorphoneState(); const id = setInterval(loadDoorphoneState, 5000); return () => clearInterval(id); }, []);
'''
    seg=seg[:insert_at]+state+seg[insert_at:]

if 'doorphoneStateMonitor' not in seg:
    ui='''      <section className="ratePanel doorphoneStateMonitor">
        <div className="doorphoneStateHead"><PanelTitle eyebrow="RAW STATE" title="状態モニター" /><button onClick={loadDoorphoneState}>更新</button></div>
        {doorphoneStateError && <div className="cameraError">{doorphoneStateError}</div>}
        {Object.keys(doorphoneStateSections).length ? <div className="doorphoneStateGrid">
          {Object.entries(doorphoneStateSections).map(([section, items]) => <article className="doorphoneStateCard" key={section}>
            <h4>{section}</h4>
            <div className="doorphoneStateRows">{Object.entries(items || {}).map(([key, item]) => <div className="doorphoneStateRow" key={key}><span>{key}</span><strong>{item?.value ?? ""}</strong></div>)}</div>
          </article>)}
        </div> : <p className="rateHelp">状態データはまだありません。</p>}
      </section>
      <section className="ratePanel doorphoneStateChanges">
        <PanelTitle eyebrow="CHANGE LOG" title="変更履歴" />
        {doorphoneStateChanges.length ? <div className="doorphoneChangeList">
          {doorphoneStateChanges.map((x, i) => <div className="doorphoneChangeRow" key={`${x.event_time}-${x.section}-${x.key}-${i}`}><small>{x.event_time}</small><span>{x.section}.{x.key}</span><strong>{x.old_value ?? ""} → {x.new_value ?? ""}</strong></div>)}
        </div> : <p className="rateHelp">変更履歴はまだありません。</p>}
      </section>
'''
    closing='    </div>\n  );\n}'
    pos=seg.rfind(closing)
    if pos<0: raise SystemExit('DoorphonePage closing block not found')
    seg=seg[:pos]+ui+seg[pos:]

s=s[:start]+seg+s[end:]
JS.write_text(s,encoding='utf-8')

c=CSS.read_text(encoding='utf-8')
marker='/* doorphone raw state monitor v3 */'
if marker not in c:
    c+='''\n\n/* doorphone raw state monitor v3 */
.doorphoneStateHead{display:flex;align-items:center;justify-content:space-between;gap:12px}.doorphoneStateHead .panelTitle{margin:0}.doorphoneStateGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:12px}.doorphoneStateCard{border:1px solid rgba(120,170,210,.2);background:rgba(5,20,35,.25);border-radius:12px;padding:12px;min-width:0}.doorphoneStateCard h4{margin:0 0 8px;color:#78c8ff;overflow-wrap:anywhere}.doorphoneStateRows{display:grid;gap:4px}.doorphoneStateRow{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid rgba(128,160,190,.12)}.doorphoneStateRow span{overflow-wrap:anywhere}.doorphoneStateRow strong{font-variant-numeric:tabular-nums;text-align:right}.doorphoneChangeList{display:grid;gap:6px;margin-top:10px}.doorphoneChangeRow{display:grid;grid-template-columns:minmax(145px,.8fr) minmax(180px,1.2fr) minmax(100px,.7fr);gap:10px;padding:7px 0;border-bottom:1px solid rgba(128,160,190,.15)}@media(max-width:650px){.doorphoneStateGrid{grid-template-columns:1fr}.doorphoneChangeRow{grid-template-columns:1fr;gap:2px}.doorphoneChangeRow small{opacity:.7}}\n'''
CSS.write_text(c,encoding='utf-8')

out=JS.read_text(encoding='utf-8')
print('patched:',JS)
print('patched:',CSS)
print('state marker:', 'doorphoneStateSections' in out)
print('ui marker:', '状態モニター' in out)
print('backup:',js_backup)
print('backup:',css_backup)
