# Copyright (c) 2026 gatekeyp contributors
# ruff: noqa: T201, S310 - a local CLI dev tool: prints results and opens a local URL
"""Live E2E door unlock: read the card, POST /api/access with the decoded
values, print the result. Usage: python door_unlock.py <card.png> <base_url>"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, "/Users/jackhuang/projects/setup")

from tests import stego_ref

card_path, base_url = sys.argv[1], sys.argv[2]
payload = stego_ref.extract(Path(card_path).read_bytes())
assert payload is not None, "no key in card"
event_id, access_key = stego_ref.parse_payload(payload)
print(f"decoded event_id: {event_id}")
print(f"decoded access_key: {access_key[:16]}...")
req = urllib.request.Request(
    f"{base_url}/api/access",
    data=json.dumps({"key": access_key, "content_id": event_id}).encode(),
    headers={"Content-Type": "application/json"},
)
resp = json.load(urllib.request.urlopen(req))
print(f"unlock status: {resp['status']}")
print(f"unlocked event id matches card: {resp['data']['id'] == event_id}")
assert resp["status"] == "success"
assert resp["data"]["id"] == event_id
print("LIVE-E2E-OK")
