#!/usr/bin/env python3
import argparse, pathlib, re, datetime, tarfile, subprocess, py_compile, shutil, os
HELPER = 'import json, sys\nimport timetree_exporter.__main__ as exporter\n\ndef main():\n    credentials = json.load(sys.stdin)\n    session = exporter.login(credentials["email"], credentials["password"])\n    client = exporter.TimeTreeCalendar(session_id=session)\n    items = client.get_metadata()\n    result = []\n    for item in items:\n        if item.get("deactivated_at") is not None:\n            continue\n        code = str(item.get("alias_code") or "")\n        if code:\n            result.append({"name": str(item.get("name") or "名称なし"), "code": code})\n    print("SIMPLEHEMS_CALENDARS=" + json.dumps(result, ensure_ascii=False))\n\nif __name__ == "__main__":\n    try:\n        main()\n    except Exception:\n        print("カレンダー一覧取得に失敗しました。認証情報または接続を確認してください。", file=sys.stderr)\n        sys.exit(1)\n'
BACKEND = "def timetree_list_calendars(body):\n old=json.loads(TC.read_text(encoding='utf-8')) if TC.exists() else {}\n email=str(body.get('email','')).strip() or str(old.get('email',''))\n password=str(body.get('password','')) or str(old.get('password',''))\n if not email or not password:raise ValueError('メールアドレスとパスワードを入力してください')\n result=subprocess.run([str(R/'.timetree-venv/bin/python'),str(R/'tools/timetree_list_calendars.py')],input=json.dumps({'email':email,'password':password}),capture_output=True,text=True,timeout=90)\n if result.returncode:raise ValueError('カレンダー一覧取得に失敗しました。認証情報または接続を確認してください')\n for line in reversed(result.stdout.splitlines()):\n  if line.startswith('SIMPLEHEMS_CALENDARS='):\n   return {'calendars':json.loads(line.split('=',1)[1])}\n raise ValueError('カレンダー一覧の応答を読み取れませんでした')\n\n"
UI_FUNCTION = "  async function loadTimetreeCalendars(){\n    setTtLoading(true);setTtMsg('カレンダー一覧を取得中...');\n    try{\n      const r=await api('/api/timetree/calendars',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:ttEmail,password:ttPassword})});\n      const items=Array.isArray(r.calendars)?r.calendars:[];setTtCalendars(items);\n      if(!items.length)setTtMsg('有効なカレンダーがありません');\n      else if(ttCode&&!items.some(x=>x.code===ttCode))setTtMsg('保存済みの対象が見つかりません。同期対象を選び直してください。');\n      else setTtMsg('同期するカレンダーを名前で選択してください');\n    }catch(e){setTtMsg('取得失敗: '+e.message)}finally{setTtLoading(false)}\n  }\n"
UI_LABEL = '<label><span>同期対象カレンダー</span><div><select value={ttCode} onChange={e=>setTtCode(e.target.value)} disabled={ttLoading}><option value="">カレンダーを選択してください</option>{ttCode&&!ttCalendars.some(x=>x.code===ttCode)&&<option value={ttCode}>保存済みの対象（一覧を取得して名前を確認）</option>}{ttCalendars.map(x=><option key={x.code} value={x.code}>{x.name}</option>)}</select></div><small>対象は自動変更しません。一覧取得後、名前を選んで保存してください。</small></label>'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--app',default='/home/hems/simplehems-server-v2')
    p.add_argument('--no-build',action='store_true')
    a=p.parse_args();root=pathlib.Path(a.app).resolve()
    server=root/'backend/server.py';src=root/'frontend/src.jsx'
    bs=server.read_text(encoding='utf-8');fs=src.read_text(encoding='utf-8')
    if 'def timetree_list_calendars(' in bs:
        raise SystemExit('既に適用済みです。変更していません。')
    if 'def timetree_credentials_public():' not in bs or 'async function saveTimetree()' not in fs:
        raise SystemExit('対象コードが想定と異なります。変更していません。')
    if not (root/'.timetree-venv/bin/python').exists():raise SystemExit('TimeTree専用venvがありません')
    if not a.no_build and not shutil.which('npm'):raise SystemExit('npmがありません。変更していません。')
    label_pattern=r'<label>\s*<span>カレンダーコード</span>.*?</label>'
    fs,n=re.subn(label_pattern,lambda m:UI_LABEL,fs,count=1,flags=re.S)
    if n!=1:raise SystemExit('カレンダーコード入力欄が見つかりません。変更していません。')
    marker='function System('
    pos=fs.find(marker);brace=fs.find('{',fs.find(') {',pos)) if ') {' in fs[pos:pos+120] else -1
    # Match the known System function declaration exactly.
    pattern=r'(function System\([^\n]*\)\s*\{)'
    fs,n=re.subn(pattern,lambda m:m.group(1)+"\n  const [ttCalendars,setTtCalendars]=useState([]),[ttLoading,setTtLoading]=useState(false);",fs,count=1)
    if n!=1:raise SystemExit('設定画面の宣言が見つかりません。変更していません。')
    fs=fs.replace('  async function saveTimetree()',UI_FUNCTION+'  async function saveTimetree()',1)
    fs=fs.replace('<span>同期対象カレンダー</span>','<span>同期対象カレンダー</span>',1)
    fs=fs.replace('<button className="saveBtn" onClick={saveTimetree}>','<button className="saveBtn" disabled={ttLoading} onClick={loadTimetreeCalendars}>カレンダー一覧を取得</button> <button className="saveBtn" disabled={ttLoading||!ttCode} onClick={saveTimetree}>',1)
    if 'onClick={loadTimetreeCalendars}' not in fs:raise SystemExit('保存ボタンが想定と異なります。変更していません。')
    bs=bs.replace('def timetree_credentials_public():',BACKEND+'def timetree_credentials_public():',1)
    route="   if self.path=='/api/timetree/credentials':"
    if route not in bs:raise SystemExit('設定APIが見つかりません。変更していません。')
    bs=bs.replace(route,"   if self.path=='/api/timetree/calendars':return self.send_data(timetree_list_calendars(body))\n"+route,1)
    backup=root.parent/('simplehems-before-r53-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.tar.gz')
    # Backup contains credentials; create it with owner-only permissions from the outset.
    fd=os.open(str(backup),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as output,tarfile.open(fileobj=output,mode='w:gz') as tar:
        for name in ('backend','frontend/src.jsx','frontend/style.css','frontend/dist','tools','secrets'):
            if (root/name).exists():tar.add(root/name,arcname=name)
    print('バックアップ:',backup,flush=True)
    original_bs=server.read_bytes();original_fs=src.read_bytes();helper=root/'tools/timetree_list_calendars.py'
    try:
        server.write_text(bs,encoding='utf-8');src.write_text(fs,encoding='utf-8');helper.write_text(HELPER,encoding='utf-8')
        py_compile.compile(str(server),doraise=True);py_compile.compile(str(helper),doraise=True)
        if not a.no_build:subprocess.run(['npm','run','build'],cwd=root/'frontend',check=True)
    except Exception:
        server.write_bytes(original_bs);src.write_bytes(original_fs);helper.unlink(missing_ok=True)
        dist=root/'frontend/dist'
        if dist.exists():shutil.rmtree(dist)
        with tarfile.open(backup,'r:gz') as tar:
            for member in tar.getmembers():
                if member.name=='frontend/dist' or member.name.startswith('frontend/dist/'):
                    tar.extract(member,root,filter='data')
        raise
    print('適用完了。simplehemsを再起動し、設定画面を再読み込みしてください。')
if __name__=='__main__':main()
