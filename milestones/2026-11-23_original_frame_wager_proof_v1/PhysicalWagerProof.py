#!/usr/bin/env python3
"""Read-only original-frame evidence. Never publishes a poker action."""
import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

SCHEMA = "PI_ORIGINAL_FRAME_WAGER_CONTRIBUTION_V1"
PAT = {
    k: re.compile(v, re.I) for k, v in {
        "hand": r"Current\s*:\s*([0-9]{8,12})",
        "bb": r"([0-9]+(?:\.[0-9]{1,2})?)\s*BB",
        "total": r"Total\s*:\s*([0-9]+(?:\.[0-9]{1,2})?)\s*BB",
        "pot": r"Pot\s+([0-9]+(?:\.[0-9]{1,2})?)\s*BB",
    }.items()
}

class Unproven(Exception):
    pass

def need(ok, why):
    if not ok:
        raise Unproven(why)

def read(p):
    return json.loads(Path(p).read_text())

def dec(v):
    try:
        d = Decimal(str(v))
    except Exception:
        raise Unproven("INVALID_AMOUNT")
    need(
        d.is_finite() and d >= 0 and
        d.as_tuple().exponent >= -2,
        "INVALID_PRECISION"
    )
    return d

def digest(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()

def lines(doc):
    return [
        v for v in doc["capture"]["lines"]
        if isinstance(v.get("text"), str)
        and v.get("confidence", 0) >= .8
        and isinstance(v.get("x"), (int, float))
        and isinstance(v.get("y"), (int, float))
    ]

def find(ls, pattern, near=None):
    out = []
    for v in ls:
        if near and (
            abs(v["x"] - near[0]) >= near[2] or
            abs(v["y"] - near[1]) >= near[3]
        ):
            continue
        m = pattern.fullmatch(v["text"].strip())
        if m:
            out.append((v, m))
    need(len(out) == 1, "MISSING_OR_NONUNIQUE_OCR")
    return out[0]

def text_near(ls, s, x, y):
    found = [
        v for v in ls
        if v["text"].strip() == s
        and abs(v["x"] - x) < .017
        and abs(v["y"] - y) < .020
    ]
    need(len(found) == 1, "SEAT_OR_LABEL_NOT_LOCATED")

class Originals:
    def __init__(self, root, swap_frame=None, alter_overlay_frame=None):
        self.root = Path(root).resolve()
        self.frames = read(self.root / "frames.json")
        self.boards = read(self.root / "local_board_observations.json")
        need(len(self.frames) == len(self.boards), "MANIFEST_LENGTH")
        self.cache = {}
        self.swap_frame = swap_frame
        self.alter_overlay_frame = alter_overlay_frame

    def get(self, n, fp, hand):
        key = (n, fp, hand)
        if key in self.cache:
            return self.cache[key]

        need(type(n) is int and 1 <= n <= len(self.frames),
             "FRAME_RANGE")
        rec = self.frames[n - 1]
        board = self.boards[n - 1]
        need(
            rec.get("id") == n and
            board.get("frame") == n and
            board.get("hand") == hand and
            board.get("sourceFingerprint") == fp,
            "FRAME_BOARD_PROVENANCE"
        )

        path = Path(
            self.frames[n - 2]["file"]
            if n == self.swap_frame else rec["file"]
        )
        need(
            not path.is_absolute() and ".." not in path.parts,
            "UNSAFE_IMAGE_PATH"
        )
        image = (self.root / path).resolve()
        need(
            self.root in image.parents and image.is_file()
            and digest(image) == fp,
            "ORIGINAL_JPEG_PROVENANCE"
        )

        ocr = read(
            self.root / "local_ocr" / f"{n:06d}.json"
        )
        need(
            ocr.get("frame") == n and
            ocr.get("sourceFingerprint") == fp,
            "OCR_PROVENANCE"
        )
        ls = lines(ocr)
        need(
            find(ls, PAT["hand"])[1].group(1) == hand,
            "HAND_MISMATCH"
        )

        if n == self.alter_overlay_frame:
            for v in ls:
                if v["text"] == "RAISE" and abs(v["x"] - .52) < .04:
                    v["text"] = "CHECK"

        row = (
            ls, board.get("visibleBoardCount"),
            rec.get("captured")
        )
        self.cache[key] = row
        return row

def proof(o, acts, totals, originals):
    need(
        o.get("kind") == "VERIFIED_SEAT_WAGER_LABEL_APPEARED",
        "NOT_PLAYER_WAGER"
    )
    n = o["from_frame"]
    m = o["to_frame"]
    hand = o["hand"]
    player = o["player"]
    f = o["from_fingerprint"]
    g = o["to_fingerprint"]

    need(
        type(n) is int and type(m) is int
        and m == n + 1 and f != g,
        "NON_ADJACENT_EPISODE"
    )
    before, street, t0 = originals.get(n, f, hand)
    after, street1, t1 = originals.get(m, g, hand)
    need(
        street in (0, 3, 4, 5) and street1 == street
        and type(t0) in (int, float)
        and type(t1) in (int, float)
        and 0 < t1 - t0 < 1.5,
        "STREET_OR_TIMING_CHANGED"
    )

    cohort = [
        a for a in acts
        if a.get("frame") == m
        and a.get("beforeFrame") == n
        and a.get("hand") == hand
    ]
    need(len(cohort) == 1, "AMBIGUOUS_SAME_FRAME_ACTIONS")
    a = cohort[0]

    need(
        a.get("player") == player
        and a.get("overlay") in ("CALL", "BET", "RAISE")
        and a.get("sameFrameOrderUnknown") is False
        and a.get("beforeFingerprint") == f
        and a.get("currentFingerprint") == g,
        "ACTION_IDENTITY_NOT_PROVEN"
    )

    w = dec(o["visible_bb"])
    label = a.get("displayedWager") or {}
    need(
        w > 0 and label.get("confidence", 0) >= .8
        and dec(label.get("amountBB")) == w
        and label.get("text") == f"{w.normalize()} BB",
        "WAGER_NOT_CERTIFIED"
    )
    need(
        dec(a["beforeStackBB"]) -
        dec(a["afterStackBB"]) == w
        and str(a.get("observedStackDeltaBB", "")).startswith("-")
        and dec(str(a["observedStackDeltaBB"])[1:]) == w,
        "STACK_DELTA_MISMATCH"
    )

    x, y = a["x"], a["y"]
    px, py = label["x"], label["y"]
    text_near(before, player, x, y)
    text_near(after, a["overlay"], x, y)
    text_near(after, label["text"], px, py)

    need(
        not [
            v for v in before
            if v["text"] == label["text"]
            and abs(v["x"] - px) < .017
            and abs(v["y"] - py) < .020
        ],
        "WAGER_ALREADY_VISIBLE"
    )

    near = (x, y - .042, .020, .023)
    stack0 = dec(find(before, PAT["bb"], near)[1].group(1))
    stack1 = dec(find(after, PAT["bb"], near)[1].group(1))
    need(
        stack0 == dec(a["beforeStackBB"])
        and stack1 == dec(a["afterStackBB"])
        and stack0 - stack1 == w,
        "ORIGINAL_STACKS_DISAGREE"
    )

    match = [
        v for v in totals
        if v.get("kind") == "VISIBLE_TOTAL_LABEL_CHANGED"
        and (
            v.get("hand"), v.get("from_frame"),
            v.get("to_frame"), v.get("from_fingerprint"),
            v.get("to_fingerprint")
        ) == (hand, n, m, f, g)
    ]
    need(len(match) == 1, "TOTAL_MATCH_NOT_UNIQUE")
    total = match[0]

    t_before = dec(
        find(before, PAT["total"])[1].group(1)
    )
    t_after = dec(
        find(after, PAT["total"])[1].group(1)
    )
    need(
        t_before == dec(total["total_before_bb"])
        and t_after == dec(total["total_after_bb"])
        and t_after - t_before ==
        dec(total["difference_bb"]) == w,
        "TOTAL_DELTA_MISMATCH"
    )

    p0 = dec(find(before, PAT["pot"])[1].group(1))
    p1 = dec(find(after, PAT["pot"])[1].group(1))
    need(p0 == p1, "POT_MOVED")

    return dict(
        hand=hand,
        player=player,
        overlay=a["overlay"],
        from_frame=n,
        to_frame=m,
        wager_contribution_bb=str(w),
        original_fingerprints=[f, g],
        not_authoritative=True,
    )

def evaluate(root, cont, cross, acts=None, originals=None):
    need(
        cont.get("schema") == "PI_NUMERIC_CONTINUITY_V1"
        and cross.get("schema") ==
        "PI_ACTION_NUMERIC_CROSSLINK_V1",
        "INPUT_SCHEMAS"
    )
    need(
        cont.get("network_calls") == 0
        and cont.get("authoritative_actions_created") == 0
        and cross.get("authoritative_actions_created") == 0,
        "NOT_READ_ONLY"
    )

    obs = cont["observations"]
    rows = cross["rows"]
    need(len(obs) == len(rows) == 14, "INPUT_EPISODE_COUNT")

    for i, (o, r) in enumerate(zip(obs, rows)):
        need(
            r.get("numeric_observation_index") == i
            and all(
                r.get(k) == o.get(k) for k in (
                    "hand", "from_frame", "to_frame",
                    "from_fingerprint", "to_fingerprint"
                )
            ),
            "CROSSLINK_OWNER_MISMATCH"
        )

    if acts is None:
        acts = read(Path(root) / "local_action_candidates.json")
    originals = originals or Originals(root)
    totals = [
        o for o in obs
        if o.get("kind") == "VISIBLE_TOTAL_LABEL_CHANGED"
    ]

    good = []
    bad = Counter()
    for o in obs:
        try:
            good.append(proof(o, acts, totals, originals))
        except Unproven as e:
            bad[str(e)] += 1

    good.sort(key=lambda v: (v["to_frame"], v["player"]))
    need(
        len(good) + sum(bad.values()) == len(obs),
        "EPISODE_COUNT_MISMATCH"
    )
    return dict(
        schema=SCHEMA,
        authority="READ_ONLY_NOT_HAND_HISTORY",
        input_observations=len(obs),
        amount_corroborated=len(good),
        withheld=sum(bad.values()),
        withheld_reasons=dict(sorted(bad.items())),
        proofs=good,
        network_calls=0,
        authoritative_actions_created=0,
    )

def negatives(root, cont, cross, base):
    acts = read(Path(root) / "local_action_candidates.json")
    need(len(base["proofs"]) == 3, "EXPECTED_THREE_PROOFS")

    end = base["proofs"][-1]["to_frame"]
    idx = next(
        i for i, a in enumerate(acts)
        if a.get("frame") == end
        and a.get("player") == "poker5068"
    )

    variants = [
        lambda a, c: a[idx].__setitem__(
            "sameFrameOrderUnknown", True
        ),
        lambda a, c: a[idx].__setitem__(
            "player", "FORGED"
        ),
        lambda a, c: a[idx].__setitem__(
            "currentFingerprint", "sha256:" + "0" * 64
        ),
        lambda a, c: a[idx]["displayedWager"].__setitem__(
            "amountBB", "8.15"
        ),
        lambda a, c: a[idx].__setitem__(
            "afterStackBB", "9.63"
        ),
        lambda a, c: a[idx]["displayedWager"].update(
            x=.919, y=.025
        ),
        lambda a, c: next(
            o for o in c["observations"]
            if o.get("kind") == "VISIBLE_TOTAL_LABEL_CHANGED"
            and o.get("to_frame") == end
        ).__setitem__("difference_bb", "8.17"),
    ]

    for mutation in variants:
        a = copy.deepcopy(acts)
        c = copy.deepcopy(cont)
        mutation(a, c)
        need(
            evaluate(root, c, cross, acts=a)[
                "amount_corroborated"
            ] == 2,
            "MUTATION_NOT_REJECTED"
        )

    extra = copy.deepcopy(acts)
    duplicate = copy.deepcopy(extra[idx])
    duplicate.update(player="ANOTHER", overlay="FOLD")
    extra.append(duplicate)
    need(
        evaluate(root, cont, cross, acts=extra)[
            "amount_corroborated"
        ] == 2,
        "SIMULTANEOUS_ACTION_NOT_REJECTED"
    )

    need(
        evaluate(
            root, cont, cross,
            originals=Originals(root, swap_frame=end)
        )["amount_corroborated"] == 2,
        "FORGED_JPEG_NOT_REJECTED"
    )
    need(
        evaluate(
            root, cont, cross,
            originals=Originals(
                root, alter_overlay_frame=end
            )
        )["amount_corroborated"] == 2,
        "FORGED_OCR_NOT_REJECTED"
    )
    return 10

def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("continuity")
    p.add_argument("crosslink")
    p.add_argument("output")
    p.add_argument("--negative", action="store_true")
    args = p.parse_args()

    cont = read(args.continuity)
    cross = read(args.crosslink)
    result = evaluate(args.root, cont, cross)

    if args.negative:
        result["negative_tests_rejected"] = negatives(
            args.root, cont, cross, result
        )

    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(
        "ORIGINAL_FRAME_AMOUNT_CORROBORATION_PASS",
        result["amount_corroborated"],
        "withheld=" + str(result["withheld"]),
        "negative=" + str(
            result.get("negative_tests_rejected", "not-run")
        ),
        "actions=0",
        flush=True
    )

if __name__ == "__main__":
    main()
