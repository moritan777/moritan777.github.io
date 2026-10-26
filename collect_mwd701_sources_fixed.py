#!/usr/bin/env python3
"""Collect SimpleHEMS/Viana source files needed for the VL-MWD701 patch."""
from __future__ import annotations
import json, re, subprocess, sys, tempfile, zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd().resolve()
VENDOR = ROOT / "vendor" / "panasonic-doorphone-connect-main"
OUTPUT = ROOT / "mwd701_source_bundle.zip"
FILES = [
 VENDOR / "crates/viana-protocol/src/discover.rs",
 VENDOR / "crates/viana-protocol/src/sip.rs",
 VENDOR / "crates/viana-protocol/src/pair.rs",
 VENDOR / "crates/viana-protocol/src/identity.rs",
 VENDOR / "crates/viana-ha/src/http.rs",
 VENDOR / "crates/viana-ha/src/config.rs",
 VENDOR / "crates/viana-ha/src/main.rs",
 VENDOR / "crates/viana-ha/src/identity.rs",
 VENDOR / "config.toml.example", VENDOR / "Cargo.toml", VENDOR / "Cargo.lock",
 VENDOR / "discover_mwd701.py", VENDOR / "discover_mwd701_uc.py",
 VENDOR / "sip_probe_all.py", VENDOR / "sip_digest_test.py",
 ROOT / "backend/server.py", ROOT / "tools/doorphone_event_bridge.py",
 ROOT / "tools/install_bundled_doorphone.sh",
]
SECRET_PATTERNS = [
 re.compile(r'(?im)^(\s*auth_token\s*=\s*)"[^"]*"'),
 re.compile(r'(?im)^(\s*base_login_password\s*=\s*)"[^"]*"'),
 re.compile(r'(?im)^(\s*password\s*=\s*)"[^"]*"'),
 re.compile(r'(?im)^(\s*token\s*=\s*)"[^"]*"'),
]
def redact(s):
 for pat in SECRET_PATTERNS: s=pat.sub(r'\1"<REDACTED>"',s)
 return s
def run(cmd):
 try:
  r=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=60)
  return {"command":cmd,"returncode":r.returncode,"stdout":r.stdout[-20000:],"stderr":r.stderr[-20000:]}
 except Exception as e: return {"command":cmd,"error":repr(e)}
def main():
 if not VENDOR.is_dir():
  print("ERROR: run from /home/hems/simplehems-server-v2",file=sys.stderr); return 2
 missing=[]
 meta={"created_at":datetime.now().astimezone().isoformat(),"root":str(ROOT),"git":run(["git","status","--short"]),"rustc":run(["rustc","--version"]),"cargo":run(["cargo","--version"]),"cargo_check":run(["cargo","check","-p","viana-ha"]),"service_definition":run(["systemctl","cat","simplehems-viana.service"]),"service_status":run(["systemctl","status","simplehems-viana.service","--no-pager","-l"])}
 with tempfile.TemporaryDirectory(prefix="mwd701_bundle_") as td:
  base=Path(td)
  for src in FILES:
   if not src.is_file(): missing.append(str(src.relative_to(ROOT))); continue
   dst=base/"sources"/src.relative_to(ROOT); dst.parent.mkdir(parents=True,exist_ok=True)
   try: dst.write_text(redact(src.read_text(encoding="utf-8")),encoding="utf-8")
   except UnicodeDecodeError: pass
  cfg=Path("/opt/viana-ha/config.toml")
  if cfg.is_file():
   dst=base/"runtime/config.toml.redacted"; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text(redact(cfg.read_text(encoding="utf-8")),encoding="utf-8")
  meta["missing_files"]=missing
  (base/"metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
  (base/"README.txt").write_text("VL-MWD701 source bundle\nSources and diagnostics only. Secrets, PCAP, DB, certificates and identity files are excluded.\n",encoding="utf-8")
  if OUTPUT.exists(): OUTPUT.unlink()
  with zipfile.ZipFile(OUTPUT,"w",zipfile.ZIP_DEFLATED) as z:
   for f in sorted(base.rglob("*")):
    if f.is_file(): z.write(f,f.relative_to(base))
 print(f"Created: {OUTPUT}")
 print(f"Size: {OUTPUT.stat().st_size} bytes")
 if missing:
  print("Missing optional files:")
  for m in missing: print(" -",m)
 return 0
if __name__ == "__main__": raise SystemExit(main())
