#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
output = Path(sys.argv[2])
helper_path = Path(sys.argv[3])

spec = importlib.util.spec_from_file_location(
    "verified_roster_helper", helper_path
)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

hand = "2874006932"
first, confirmed = 91, 92
unknown = "UNRESOLVED_LOWER_LEFT_SEAT"

frames = h.read(root/"frames.json")
boards = h.read(root/"local_board_observations.json")
cards = h.read(root/"observed_card_back_pairs.json")
blinds = h.read(root/"observed_button_from_blinds.json")

assert len(frames) == len(boards) == len(cards) == 237
assert not output.exists()

ocr = {}
physical = {}

for n in (first, confirmed):
    doc = h.read(root/f"local_ocr/{n:06d}.json")
    fingerprint = h.digest(root/frames[n-1]["file"])

    assert frames[n-1]["id"] == n
    assert doc["frame"] == n
    assert doc["sourceFingerprint"] == fingerprint
    assert boards[n-1]["sourceFingerprint"] == fingerprint
    assert cards[n-1]["sourceFingerprint"] == fingerprint
    assert h.hand_of(doc) == hand
    assert boards[n-1]["hand"] == hand
    assert cards[n-1]["hand"] == hand
    assert boards[n-1]["visibleBoardCount"] == 0
    assert doc["capture"].get("error") is None

    ocr[n] = doc
    physical[n] = (
        cards[n-1]["pairs"] +
        (cards[n-1].get("faceUpPairs") or [])
    )

assert len(physical[first]) == len(physical[confirmed]) == 8

lines = ocr[confirmed]["capture"]["lines"]
previous_lines = ocr[first]["capture"]["lines"]

seats = []
used_before = set()
used_after = set()

for label in lines:
    name = label["text"].strip()

    truncated = bool(
        re.fullmatch(r"[A-Za-z0-9_]{3,31}\.\.\.",name)
    )

    if not (h.NAME.fullmatch(name) or truncated):
        continue

    if (
        label["confidence"] < .8
        or not re.search(r"[A-Za-z]",name)
        or re.sub(r"[^A-Z0-9]","",name.upper()) in h.UI
    ):
        continue

    stacks = [
        x for x in lines
        if x["confidence"] >= .8
        and h.STACK.fullmatch(x["text"].strip())
        and abs(x["x"]-label["x"]) < .028
        and .025 < label["y"]-x["y"] < .058
    ]

    if len(stacks) != 1:
        continue

    matches = [
        [
            i for i,c in enumerate(physical[n])
            if h.near(c,label)
        ]
        for n in (first,confirmed)
    ]

    if any(len(m) != 1 for m in matches):
        continue

    a,b = matches[0][0],matches[1][0]

    assert a not in used_before
    assert b not in used_after

    before = physical[first][a]
    after = physical[confirmed][b]

    assert abs(before["x"]-after["x"]) < .018
    assert abs(before["y"]-after["y"]) < .018

    stable = [
        x for x in previous_lines
        if x["text"] == name
        and x["confidence"] >= .8
        and abs(x["x"]-label["x"]) < .012
        and abs(x["y"]-label["y"]) < .012
    ]

    assert len(stable) == 1

    used_before.add(a)
    used_after.add(b)

    seats.append({
        "name":unknown if truncated else name,
        "visible_label":name,
        "x":label["x"],
        "y":label["y"],
        "identity_verified":not truncated
    })

assert len(seats) == 8
assert len(used_before) == len(used_after) == 8
assert sum(not s["identity_verified"] for s in seats) == 1
assert sum(s["identity_verified"] for s in seats) == 7

cx = (min(s["x"] for s in seats) +
      max(s["x"] for s in seats))/2
cy = (min(s["y"] for s in seats) +
      max(s["y"] for s in seats))/2

ring = [
    s["name"] for s in sorted(
        seats,
        key=lambda s:math.atan2(
            s["y"]-cy,s["x"]-cx
        ),
        reverse=True
    )
]

proofs = [
    b for b in blinds
    if b["hand"] == hand
    and b["firstFrame"] == first
    and b["confirmedFrame"] == confirmed
]

assert len(proofs) == 1
proof = proofs[0]

assert proof["firstFingerprint"] == \
       ocr[first]["sourceFingerprint"]
assert proof["confirmedFingerprint"] == \
       ocr[confirmed]["sourceFingerprint"]

named_ring = [x for x in ring if x != unknown]

assert h.cyclic_same(named_ring,proof["clockwiseRing"])

i = ring.index(proof["dealer"])

assert ring[(i+1)%len(ring)] == proof["smallBlind"]
assert ring[(i+2)%len(ring)] == proof["bigBlind"]

assert ring == [
    "Vs96691",
    "Pokerqueen1331",
    "Simplysim",
    "SVOBODA007",
    "danny508",
    "poker5068",
    unknown,
    "natcool"
], "Original physical seat ring differs"

roster = {
    "hand":hand,
    "priorFrame":first,
    "rosterFrame":confirmed,
    "clockwiseRing":ring,
    "dealer":proof["dealer"],
    "smallBlind":proof["smallBlind"],
    "bigBlind":proof["bigBlind"],
    "sourceFingerprints":[
        ocr[first]["sourceFingerprint"],
        ocr[confirmed]["sourceFingerprint"]
    ]
}

output.write_text(
    json.dumps([roster],indent=2,sort_keys=True)+"\n"
)

provenance = {
    "hand":hand,
    "fully_verified_named_seats":named_ring,
    "unresolved_physical_seat":unknown,
    "truncated_nameplate":"StealthDevilDog...",
    "truncated_name_is_not_full_identity":True,
    "original_frames":[first,confirmed],
    "physical_card_pairs_per_frame":8,
    "blind_ring_consistent":True,
    "source_fingerprints":roster["sourceFingerprints"],
    "authoritative_action_changes":0
}

(output.parent/"roster_provenance.json").write_text(
    json.dumps(provenance,indent=2,sort_keys=True)+"\n"
)

print("EIGHT_SEAT_PHYSICAL_ROSTER_PASS")
print("HAND:",hand)
print("SEATS: 8")
print("VERIFIED NAMES: 7")
print("UNKNOWN IDENTITIES: 1")
print("BLIND ORDER: VERIFIED")
