#!/usr/bin/env python3
"""Offline, hand-scoped, original-frame roster recovery."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

STACK = re.compile(r"^[0-9]{1,4}(?:\.[0-9]{1,3})?\s+BB$", re.I)
HAND = re.compile(r"^Current:\s*([0-9]{8,12})$")
NAME = re.compile(r"^[A-Za-z0-9_]{3,31}$")

UI = {
    "FOLD","CALL","RAISE","RAISER","CHECK","BET","ALLIN",
    "WINNER","WINER","ANTE","ANTER","POT","TOTAL",
    "CURRENT","PREVIOUS","DEALER","SITOUT","TIMEBANK",
    "SHOW","DONTSHOW","POSTBB","POSTSB","POSTANTE","SB","BB"
}

def require(ok, msg):
    if not ok:
        raise ValueError(msg)

def read(path):
    return json.loads(path.read_text())

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()

def hand_of(frame):
    found = [
        m.group(1)
        for x in frame["capture"]["lines"]
        for m in [HAND.fullmatch(x["text"].strip())]
        if m
    ]
    return found[0] if len(found) == 1 else None

def near(card, label):
    return (
        abs(card["x"]-label["x"]) < .030
        and .030 < (1-label["y"])-card["y"] < .085
    )

def cyclic_same(a, b):
    return (
        len(a) == len(b)
        and any(a[i:]+a[:i] == b for i in range(len(a)))
    )

def recover(root, shadow, hand_id, before_n, roster_n):
    require(before_n+1 == roster_n, "Frames must be adjacent")
    require(not shadow.exists(), "Shadow already exists")
    require(root.resolve() != shadow.resolve(), "Original overwrite blocked")

    frames = read(root/"frames.json")
    boards = read(root/"local_board_observations.json")
    cards = read(root/"observed_card_back_pairs.json")
    blinds = read(root/"observed_button_from_blinds.json")

    require(len(frames) == len(boards) == len(cards),
            "Frame array counts differ")

    ocr = {}

    for n in (before_n, roster_n):
        item = read(root/f"local_ocr/{n:06d}.json")
        fingerprint = digest(root/frames[n-1]["file"])

        require(frames[n-1]["id"] == n and item["frame"] == n,
                "Frame ID mismatch")

        require(
            fingerprint == item["sourceFingerprint"] ==
            boards[n-1]["sourceFingerprint"] ==
            cards[n-1]["sourceFingerprint"],
            "Original frame provenance mismatch"
        )

        require(
            boards[n-1]["visibleBoardCount"] == 0 and
            hand_of(item) == hand_id and
            boards[n-1]["hand"] == hand_id and
            cards[n-1]["hand"] == hand_id,
            "Hand boundary or board evidence mismatch"
        )

        ocr[n] = item

    require(
        ocr[before_n]["sourceFingerprint"] !=
        ocr[roster_n]["sourceFingerprint"],
        "Duplicate frames"
    )

    before = (
        cards[before_n-1]["pairs"] +
        (cards[before_n-1].get("faceUpPairs") or [])
    )

    current = (
        cards[roster_n-1]["pairs"] +
        (cards[roster_n-1].get("faceUpPairs") or [])
    )

    require(
        len(before) == len(current) and
        3 <= len(current) <= 10,
        "Unstable dealt-in card count"
    )

    lines = ocr[roster_n]["capture"]["lines"]
    seats = []
    used_before = set()
    used_current = set()

    for label in lines:
        name = label["text"].strip()

        if (
            label["confidence"] < .8 or
            not NAME.fullmatch(name) or
            not re.search("[A-Za-z]", name) or
            re.sub("[^A-Z0-9]", "", name.upper()) in UI
        ):
            continue

        stacks = [
            x for x in lines
            if x["confidence"] >= .8
            and STACK.fullmatch(x["text"].strip())
            and abs(x["x"]-label["x"]) < .028
            and .025 < label["y"]-x["y"] < .058
        ]

        if len(stacks) != 1:
            continue

        prior_matches = [
            i for i, card in enumerate(before)
            if near(card, label)
        ]

        now_matches = [
            i for i, card in enumerate(current)
            if near(card, label)
        ]

        if len(prior_matches) != 1 or len(now_matches) != 1:
            continue

        i = prior_matches[0]
        j = now_matches[0]

        require(
            i not in used_before and j not in used_current,
            "Card evidence claimed by two players"
        )

        require(
            abs(before[i]["x"]-current[j]["x"]) < .018 and
            abs(before[i]["y"]-current[j]["y"]) < .018,
            "Physical card coordinates unstable"
        )

        used_before.add(i)
        used_current.add(j)
        seats.append(label)

    require(
        len(seats) == len(current) and
        len(used_before) == len(before) and
        len(used_current) == len(current),
        "Some dealt-in players lack physical attribution"
    )

    require(
        len({x["text"].lower() for x in seats}) == len(seats),
        "Duplicate player names"
    )

    cx = (
        min(x["x"] for x in seats) +
        max(x["x"] for x in seats)
    ) / 2

    cy = (
        min(x["y"] for x in seats) +
        max(x["y"] for x in seats)
    ) / 2

    ring = [
        x["text"] for x in sorted(
            seats,
            key=lambda x:math.atan2(x["y"]-cy,x["x"]-cx),
            reverse=True
        )
    ]

    proofs = [
        b for b in blinds
        if b["hand"] == hand_id
        and b["firstFrame"] > roster_n
        and b["confirmedFrame"] > b["firstFrame"]
    ]

    require(len(proofs) == 1, "Unique blind proof missing")

    b = proofs[0]

    for n, field in (
        (b["firstFrame"],"firstFingerprint"),
        (b["confirmedFrame"],"confirmedFingerprint")
    ):
        item = read(root/f"local_ocr/{n:06d}.json")

        require(
            item["sourceFingerprint"] == b[field]
            and hand_of(item) == hand_id,
            "Later blind proof belongs to another hand"
        )

    filtered = [
        player for player in ring
        if player in b["clockwiseRing"]
    ]

    require(
        cyclic_same(filtered,b["clockwiseRing"]),
        "Early roster contradicts later physical ring"
    )

    dealer = b["dealer"]
    sb = b["smallBlind"]
    bb = b["bigBlind"]

    require(
        dealer in ring and sb in ring and bb in ring,
        "Dealer or blind missing"
    )

    i = ring.index(dealer)

    require(
        ring[(i+1)%len(ring)] == sb and
        ring[(i+2)%len(ring)] == bb,
        "Blind positions inconsistent"
    )

    roster = {
        "hand":hand_id,
        "rosterFrame":roster_n,
        "priorFrame":before_n,
        "clockwiseRing":ring,
        "dealer":dealer,
        "smallBlind":sb,
        "bigBlind":bb,
        "sourceFingerprints":[
            ocr[before_n]["sourceFingerprint"],
            ocr[roster_n]["sourceFingerprint"]
        ]
    }

    shadow.mkdir(parents=True)

    for name in (
        "frames.json","frames","local_ocr",
        "local_board_observations.json"
    ):
        path = root/name
        if path.exists():
            (shadow/name).symlink_to(
                path.resolve(),
                target_is_directory=path.is_dir()
            )

    (shadow/"observed_verified_dealt_in_rosters.json").write_text(
        json.dumps([roster],indent=2,sort_keys=True)+"\n"
    )

    provenance = {
        "original_recording":root.name,
        "original_recording_unchanged":True,
        "hand":hand_id,
        "roster":roster,
        "blind_confirmation_frame":b["confirmedFrame"],
        "scope":"RETROSPECTIVE_NUMERIC_OBSERVATION_ONLY",
        "authoritative_action_changes":0
    }

    (shadow/"roster_provenance.json").write_text(
        json.dumps(provenance,indent=2,sort_keys=True)+"\n"
    )

    print(
        "EARLY_ROSTER_PHYSICAL_PASS "
        f"hand={hand_id} seats={len(ring)} "
        f"prior={before_n} roster={roster_n} "
        f"blind_confirmed={b['confirmedFrame']}"
    )

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--recording",type=Path,required=True)
    p.add_argument("--shadow",type=Path,required=True)
    p.add_argument("--hand",required=True)
    p.add_argument("--prior",type=int,required=True)
    p.add_argument("--roster",type=int,required=True)
    a = p.parse_args()

    recover(
        a.recording,a.shadow,a.hand,a.prior,a.roster
    )

if __name__ == "__main__":
    main()
