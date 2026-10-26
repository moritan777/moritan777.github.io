#!/usr/bin/env python3
"""VL-MWD701 LAN pairing diagnostic.

Runs only the legacy/LAN path:
  pnvi discovery -> unauthenticated SIP MESSAGE -> assigned terminal
  -> RFC2617 REGISTER -> NOTIFY ACK

It intentionally does NOT call VIANA mint, CGI 107/108, or cloud endpoints.
Run only against equipment you own/administer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import select
import socket
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SIP_PORT = 5060
DISCOVERY_UDP_PORT = 50000
DEFAULT_CALLBACK_PORT = 52000
REGISTER_EXPIRES = 30
USER_AGENT = "Panasonic_ドアホン/2.1"


def log(event: str, **fields) -> None:
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields}
    print(json.dumps(row, ensure_ascii=False), flush=True)


def local_ipv4_for(target: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 9))
        return s.getsockname()[0]
    finally:
        s.close()


def normalize_mac(value: str) -> str:
    out = re.sub(r"[^0-9a-fA-F]", "", value).lower()
    if len(out) != 12:
        raise ValueError("MAC must contain exactly 12 hex digits")
    return out


def load_or_create_mac(path: Path, supplied: str | None) -> str:
    if supplied:
        return normalize_mac(supplied)
    if path.exists():
        return normalize_mac(path.read_text(encoding="ascii").strip())
    b = bytearray(os.urandom(6))
    b[0] = (b[0] | 0x02) & 0xFE  # locally administered, unicast
    mac = b.hex()
    path.write_text(mac + "\n", encoding="ascii")
    os.chmod(path, 0o600)
    return mac


def discover_pnvi(target_ip: str | None, target_mac: str, timeout: float, callback_port: int):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", callback_port))
    listener.listen(2)
    listener.setblocking(False)

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    destination = target_ip or "255.255.255.255"
    payload = f"pnvi,{callback_port},{target_mac}"
    log("discover.send", destination=destination, udp_port=DISCOVERY_UDP_PORT,
        callback_port=callback_port, payload=payload)
    udp.sendto(payload.encode("ascii"), (destination, DISCOVERY_UDP_PORT))
    udp.close()

    ready, _, _ = select.select([listener], [], [], timeout)
    if not ready:
        listener.close()
        log("discover.timeout")
        return None
    conn, peer = listener.accept()
    conn.settimeout(2)
    raw = conn.recv(4096)
    conn.close()
    listener.close()
    text = raw.split(b"\0", 1)[0].decode("utf-8", "replace").strip()
    log("discover.response", peer=peer[0], raw=text)
    parts = [x.strip() for x in text.split(",")]
    return {
        "lan_ip": parts[0] if parts and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", parts[0]) else peer[0],
        "mac": parts[1] if len(parts) > 1 else None,
        "model": parts[2] if len(parts) > 2 else None,
        "status": parts[3] if len(parts) > 3 else None,
        "raw": text,
    }


def md5_hex(text: str, upper: bool = False) -> str:
    value = hashlib.md5(text.encode("utf-8")).hexdigest()
    return value.upper() if upper else value


def sip_password(mac: str) -> str:
    return md5_hex(mac, upper=True)


def random_hex(n: int) -> str:
    return "".join(random.choice(string.hexdigits.lower()[:16]) for _ in range(n))


def call_id(local_ip: str) -> str:
    return f"{random_hex(8)}-{random_hex(20)}303030303030@[{local_ip}]"


def recv_frame(sock: socket.socket, timeout: float = 5.0):
    sock.settimeout(timeout)
    data, peer = sock.recvfrom(16384)
    return data.decode("utf-8", "replace"), peer


def header(message: str, name: str) -> str | None:
    unfolded = re.sub(r"\r?\n[ \t]+", " ", message)
    m = re.search(rf"(?im)^{re.escape(name)}\s*:\s*(.+?)\s*$", unfolded)
    return m.group(1).strip() if m else None


def digest_fields(challenge: str) -> dict[str, str]:
    line = header(challenge, "WWW-Authenticate") or ""
    out: dict[str, str] = {}
    for key in ("realm", "nonce", "qop", "algorithm"):
        m = re.search(rf"(?i)\b{key}\s*=\s*(?:\"([^\"]*)\"|([^,\s]+))", line)
        if m:
            out[key] = m.group(1) if m.group(1) is not None else m.group(2)
    return out


def digest_response(username: str, realm: str, password: str, method: str,
                    uri: str, nonce: str, nc: str, cnonce: str, qop: str) -> str:
    ha1 = md5_hex(f"{username}:{realm}:{password}")
    ha2 = md5_hex(f"{method}:{uri}")
    if qop:
        return md5_hex(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
    return md5_hex(f"{ha1}:{nonce}:{ha2}")


@dataclass
class SipContext:
    base_ip: str
    local_ip: str
    local_port: int
    mac: str
    name: str
    call_id: str
    tag: str

    @classmethod
    def make(cls, base_ip: str, local_ip: str, local_port: int, mac: str, name: str):
        return cls(base_ip, local_ip, local_port, mac, name, call_id(local_ip), str(random.getrandbits(32)))


def send_pair_message(sock: socket.socket, ctx: SipContext) -> int | None:
    branch = "z9hG4bK" + random_hex(8)
    body = f'Register:MAC={ctx.mac};Name="{ctx.name}"\r\n'
    request = (
        f"MESSAGE sip:Server@{ctx.base_ip}> SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {ctx.local_ip}:{ctx.local_port};branch={branch}\r\n"
        "Max-Forwards: 70\r\n"
        f"To: <sip:Server@{ctx.base_ip}>>\r\n"
        f"From: <sip:Client@{ctx.base_ip}>;tag={ctx.tag}\r\n"
        f"Call-ID: {ctx.call_id}\r\n"
        "CSeq: 1 MESSAGE\r\n"
        "Allow: INVITE,ACK,CANCEL,BYE,INFO,MESSAGE,NOTIFY,UPDATE\r\n"
        "Content-Type: application/text\r\n"
        f"User-Agent: {USER_AGENT}\r\n"
        f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}"
    )
    log("sip.message.send", base=ctx.base_ip, local_port=ctx.local_port,
        body=body.rstrip(), bytes=len(request.encode("utf-8")))
    sock.sendto(request.encode("utf-8"), (ctx.base_ip, SIP_PORT))
    response, peer = recv_frame(sock)
    status = response.splitlines()[0] if response else ""
    psnum = header(response, "PSN-Notify-PSnum")
    assigned = int(psnum) if psnum and psnum.isdigit() else None
    log("sip.message.response", peer=peer[0], status=status, assigned_terminal=assigned,
        headers={"PSN-Notify-PSnum": psnum})
    return assigned


def build_register(ctx: SipContext, terminal: int, cseq: int,
                   auth: dict[str, str] | None = None, nc_value: int | None = None) -> str:
    branch = "z9hG4bK" + random_hex(8)
    uri = f"sip:{ctx.base_ip};transport=udp"
    auth_line = ""
    if auth:
        nc = f"{(nc_value if nc_value is not None else cseq - 1):08x}"
        cnonce = random_hex(8).upper()
        qop = auth.get("qop", "").split(",", 1)[0].strip()
        response = digest_response(str(terminal), auth["realm"], auth["password"],
                                   "REGISTER", uri, auth["nonce"], nc, cnonce, qop)
        if qop:
            auth_line = (f'Authorization: Digest realm="{auth["realm"]}", nonce="{auth["nonce"]}", '
                         f'algorithm=MD5, qop={qop}, cnonce="{cnonce}", nc={nc}, uri="{uri}", '
                         f'username="{terminal}", response="{response}"\r\n')
        else:
            auth_line = (f'Authorization: Digest realm="{auth["realm"]}", nonce="{auth["nonce"]}", '
                         f'algorithm=MD5, uri="{uri}", username="{terminal}", response="{response}"\r\n')
    return (
        f"REGISTER {uri} SIP/2.0\r\n"
        f"Via: SIP/2.0/UDP {ctx.local_ip}:{ctx.local_port};branch={branch}\r\n"
        "Max-Forwards: 70\r\n"
        f"To: <sip:{terminal}@{ctx.base_ip}>\r\n"
        f"From: <sip:{terminal}@{ctx.base_ip}>;tag={ctx.tag}\r\n"
        f"Call-ID: {ctx.call_id}\r\n"
        f"CSeq: {cseq} REGISTER\r\n"
        f"Contact: <sip:{terminal}@{ctx.local_ip}:{ctx.local_port}>\r\n"
        f"Expires: {REGISTER_EXPIRES}\r\n"
        f"{auth_line}"
        "Allow: INVITE,ACK,CANCEL,BYE,INFO,MESSAGE,NOTIFY,UPDATE\r\n"
        f"User-Agent: {USER_AGENT}\r\n"
        "Content-Length: 0\r\n\r\n"
    )


def ack_notify(sock: socket.socket, frame: str, peer, fallback_tag: str) -> None:
    via = header(frame, "Via") or ""
    to = header(frame, "To") or ""
    from_h = header(frame, "From") or ""
    callid = header(frame, "Call-ID") or ""
    cseq = header(frame, "CSeq") or ""
    if ";tag=" not in to:
        to += f";tag={fallback_tag}"
    response = ("SIP/2.0 200 OK\r\n" f"Via: {via}\r\n" f"To: {to}\r\n"
                f"From: {from_h}\r\n" f"Call-ID: {callid}\r\n" f"CSeq: {cseq}\r\n"
                "Content-Length: 0\r\n\r\n")
    sock.sendto(response.encode("utf-8"), peer)
    log("sip.notify.ack", cseq=cseq, event=header(frame, "Event"))


def wait_register_response(sock: socket.socket, ctx: SipContext, timeout_s: float = 5.0) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        frame, peer = recv_frame(sock, remaining)
        first = frame.splitlines()[0] if frame else ""
        if first.startswith("NOTIFY"):
            log("sip.notify", first_line=first, event_header=header(frame, "Event"),
                body=frame.split("\r\n\r\n", 1)[1][:2048] if "\r\n\r\n" in frame else "")
            ack_notify(sock, frame, peer, ctx.tag)
            continue
        if first.startswith("SIP/") and "100 Trying" not in first:
            return frame
        log("sip.unexpected", first_line=first)
    raise TimeoutError("REGISTER response timeout")


def register(sock: socket.socket, ctx: SipContext, terminal: int):
    req1 = build_register(ctx, terminal, 1)
    sock.sendto(req1.encode("utf-8"), (ctx.base_ip, SIP_PORT))
    challenge = wait_register_response(sock, ctx)
    status1 = challenge.splitlines()[0] if challenge else ""
    fields = digest_fields(challenge)
    log("sip.register.challenge", status=status1, realm=fields.get("realm"),
        qop=fields.get("qop"), nonce_present=bool(fields.get("nonce")))
    if not fields.get("realm") or not fields.get("nonce"):
        raise RuntimeError("REGISTER challenge did not contain usable WWW-Authenticate")
    auth = {**fields, "password": sip_password(ctx.mac)}
    for cseq in (2, 3):
        req = build_register(ctx, terminal, cseq, auth)
        sock.sendto(req.encode("utf-8"), (ctx.base_ip, SIP_PORT))
        response = wait_register_response(sock, ctx)
        status = response.splitlines()[0] if response else ""
        log("sip.register.response", cseq=cseq, status=status)
        if "200" not in status:
            raise RuntimeError(f"REGISTER CSeq {cseq} failed: {status}")
    return auth


def observe_notifies(sock: socket.socket, ctx: SipContext, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    log("observe.start", seconds=seconds)
    while time.monotonic() < deadline:
        try:
            frame, peer = recv_frame(sock, min(1.0, deadline - time.monotonic()))
        except socket.timeout:
            continue
        first = frame.splitlines()[0] if frame else ""
        if first.startswith("NOTIFY"):
            body = frame.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in frame else ""
            log("sip.notify", event_header=header(frame, "Event"), body=body[:4096])
            ack_notify(sock, frame, peer, ctx.tag)
        else:
            log("sip.unexpected", first_line=first)
    log("observe.end")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-ip", help="Known base IPv4; also used for unicast pnvi")
    ap.add_argument("--target-mac", default="00:00:00:00:00:00",
                    help="Known base MAC for pnvi, or wildcard")
    ap.add_argument("--callback-port", type=int, default=DEFAULT_CALLBACK_PORT)
    ap.add_argument("--discover-timeout", type=float, default=8.0)
    ap.add_argument("--name", default="SimpleHEMS")
    ap.add_argument("--synthetic-mac", help="12 hex digits; omitted = persisted local value")
    ap.add_argument("--mac-file", default="mwd701_synthetic_mac.txt")
    ap.add_argument("--terminal", type=int, help="Fallback slot 21..28 if MESSAGE lacks PSnum")
    ap.add_argument("--observe", type=float, default=20.0,
                    help="Seconds to ACK/log NOTIFY after REGISTER")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--yes", action="store_true", help="Required to transmit pairing SIP")
    args = ap.parse_args()

    discovered = discover_pnvi(args.target_ip, args.target_mac,
                               args.discover_timeout, args.callback_port)
    base_ip = (discovered or {}).get("lan_ip") or args.target_ip
    if args.discover_only:
        return 0 if discovered else 3
    if not base_ip:
        log("fatal", message="No base discovered and --target-ip not supplied")
        return 3
    if not args.yes:
        log("fatal", message="Refusing to pair without --yes")
        return 2

    mac = load_or_create_mac(Path(args.mac_file), args.synthetic_mac)
    local_ip = local_ipv4_for(base_ip)
    log("pair.start", base_ip=base_ip, local_ip=local_ip, synthetic_mac=mac,
        name=args.name, cgi_used=False, cloud_used=False)

    msg_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    msg_sock.bind(("0.0.0.0", 0))
    msg_ctx = SipContext.make(base_ip, local_ip, msg_sock.getsockname()[1], mac, args.name)
    assigned = send_pair_message(msg_sock, msg_ctx)
    msg_sock.close()
    terminal = assigned or args.terminal
    if terminal is None or not 21 <= terminal <= 28:
        log("fatal", message="No valid terminal 21..28; use --terminal only if known from capture")
        return 4

    reg_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    reg_sock.bind(("0.0.0.0", 0))
    reg_ctx = SipContext.make(base_ip, local_ip, reg_sock.getsockname()[1], mac, args.name)
    register(reg_sock, reg_ctx, terminal)
    log("pair.sip_registered", terminal=terminal, cgi_used=False, cloud_used=False)
    observe_notifies(reg_sock, reg_ctx, args.observe)
    reg_sock.close()
    log("diagnostic.complete", terminal=terminal,
        note="SIP registration observed only; no CGI/VIANA state persisted")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("interrupted")
        raise SystemExit(130)
    except Exception as exc:
        log("fatal", error=type(exc).__name__, message=str(exc))
        raise SystemExit(1)
