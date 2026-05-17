from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests


def fail(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--server-url", default="http://127.0.0.1:8767")
    p.add_argument("--token", required=True)
    p.add_argument("--call-id", default="smoke-test-call")
    args = p.parse_args()

    base = args.server_url.rstrip("/")
    call_id = args.call_id

    r = requests.get(f"{base}/health", timeout=10)
    if r.status_code != 200:
        return fail(f"health status={r.status_code}")
    print("[OK] health")

    event_payload = {
        "token": args.token,
        "device_id": "smoke-agent",
        "event_type": "incoming",
        "phone_number": "+900000000000",
        "state": "ringing",
        "call_id": call_id,
        "extra": {"akis_id": "varsayilan"},
    }
    r = requests.post(f"{base}/api/v1/events", json=event_payload, timeout=10)
    if r.status_code != 200:
        return fail(f"event status={r.status_code} body={r.text[:200]}")
    print("[OK] event incoming")

    r = requests.post(
        f"{base}/api/v1/calls/{call_id}/prompt",
        json={"token": args.token},
        timeout=30,
    )
    if r.status_code != 200:
        return fail(f"prompt status={r.status_code} body={r.text[:200]}")
    prompt = r.json()
    if not prompt.get("ok"):
        return fail("prompt ok=false")
    print("[OK] prompt")

    r = requests.get(
        f"{base}/api/v1/calls/{call_id}/prompt-audio",
        params={"token": args.token},
        timeout=30,
    )
    if r.status_code != 200:
        return fail(f"prompt-audio status={r.status_code} body={r.text[:200]}")
    if len(r.content) == 0:
        return fail("prompt-audio empty")
    prompt_audio = r.content
    print(f"[OK] prompt-audio bytes={len(r.content)}")

    r = requests.post(
        f"{base}/api/v1/calls/{call_id}/menu",
        json={"token": args.token, "digit": "1"},
        timeout=10,
    )
    if r.status_code != 200:
        return fail(f"menu status={r.status_code} body={r.text[:200]}")
    menu = r.json()
    if not menu.get("ok"):
        return fail("menu ok=false")
    print("[OK] menu")

    r = requests.get(f"{base}/api/v1/calls/{call_id}", timeout=10)
    if r.status_code != 200:
        return fail(f"call-get status={r.status_code}")
    call = r.json()
    if not call.get("ok"):
        return fail("call-get ok=false")
    meta = call.get("meta", {})
    if not meta.get("prompt_tts_hazir"):
        print("[WARN] prompt_tts_hazir false")
    if meta.get("son_secim") != "1":
        return fail(f"son_secim beklenen=1 gercek={meta.get('son_secim')!r}")
    print("[OK] call state/meta")

    out_dir = Path("/tmp")
    (out_dir / "zk-santral-smoke-call.json").write_text(
        json.dumps(call, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "zk-santral-smoke-prompt.bin").write_bytes(prompt_audio)
    print("[OK] smoke completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
