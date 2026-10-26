#!/usr/bin/env python3
"""Collect the exact SimpleHEMS/Viana sources needed for the VL-MWD701 patch.

Run from /home/hems/simplehems-server-v2.
This script is read-only. It does not modify the repository or /opt/viana-ha.
Secrets and generated identity files are intentionally excluded.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
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
    VENDOR / "config.toml.example",
    VENDOR / "Cargo.toml",
    VENDOR / "Cargo.lock",
    VENDOR / "discover_mwd701.py",
    VENDOR / "discover_mwd701_uc.py",
    VENDOR / "sip_probe_all.py",
    VENDOR / "sip_digest_test.py",
    ROOT / "backend/server.py",
    ROOT / "tools/doorphone_event_bridge.py",
    ROOT / "tools/install_bundled_doorphone.sh",
]

SECRET_PATTERNS = [
    re.compile(r'(?im)^(\s*auth_token\s*=\s*)"[^"]*"'),
    re.compile(r'(?im)^(\s*base_login_password\s*=\s*)"[^"]*"'),
    re.compile(r'(?im)^(\s*password\s*=\s*)"[^"]*"'),
    re.compile(r'(?im)^(\s*token\s*=\s*)"[^"]*"'),
]


def redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r'\1"<REDACTED>"', text)
    return text


def run(cmd: list[str]) -> dict:
    try:
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=60)
        return {
            "command": cmd,
            "returncode": p.returncode,
            "stdout": p.stdout[-20000:],
            "stderr": p.stderr[-20000:],
        }
    except Exception as e:
        return {"command": cmd, "error": repr(e)}


def main() -> int:
    expected = ROOT / "vendor" / "panasonic-doorphone-connect-main"
    if not expected.is_dir():
        print("ERROR: Run this script from /home/hems/simplehems-server-v2", file=sys.stderr)
        return 2

    missing = [str(p.relative_to(ROOT)) for p in FILES if not p.is_file()]
    metadata = {
        "created_at": datetime.now().astimezone().isoformat(),
        "root": str(ROOT),
        "missing_files": missing,
        "git": run(["git", "status", "--short"]),
        "rustc": run(["rustc", "--version"]),
        "cargo": run(["cargo", "--version"]),
        "cargo_check": run(["cargo", "check", "-p", "viana-ha"]),
        "service_definition": run(["systemctl", "cat", "simplehems-viana.service"]),
        "service_status": run(["systemctl", "status", "simplehems-viana.service", "--no-pager", "-l"]),
    }

    with tempfile.TemporaryDirectory(prefix="mwd701_bundle_") as temp_name:
        temp = Path(temp_name)
        source_dir = temp / "sources"
        source_dir.mkdir(parents=True)

        for src in FILES:
            if not src.is_file():
                continue
            rel = src.relative_to(ROOT)
            dst = source_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                text = src.read_text(encoding="utf-8")
                dst.write_text(redact(text), encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(src, dst)

        # Include redacted active configuration only. Never collect kiki.dat, ca.pem,
        # PCAPs, databases, identity material, or other secrets.
        active_cfg = Path("/opt/viana-ha/config.toml")
        if active_cfg.is_file():
            text = active_cfg.read_text(encoding="utf-8")
            dst = temp / "runtime" / "config.toml.redacted"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(redact(text), encoding="utf-8")

        (temp / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (temp / "README.txt").write_text(
            """VL-MWD701 source bundle\n\n"
            "This archive contains source files and diagnostics only.\n"
            "It intentionally excludes PCAP files, databases, kiki.dat, certificates,\n"
            "tokens, passwords, and identity material.\n"
            "\n"
            "Purpose: make a source-accurate patch that adds an MWD701 pairing path\n"
            "without breaking the existing Viana CGI path.\n",
            encoding="utf-8",
        )

        if OUTPUT.exists():
            OUTPUT.unlink()
        with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(temp.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(temp))

    print(f"Created: {OUTPUT}")
    print(f"Size: {OUTPUT.stat().st_size} bytes")
    if missing:
        print("Missing optional files:")
        for item in missing:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
