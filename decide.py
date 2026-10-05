#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decision arbitration for the local decision-layer.

Reads policy.json and prints a verdict:
  {mode, confidence, threshold, risky, is_gap, learned_choice, recommended, note}

Enhancements (borrowed from public projects, kept zero-API / file-only):
- Gap Protocol: an unknown class (is_gap) is flagged so the first run must
  confirm AND record the user's preference.
- learned_choice: returns the user's historically chosen id for this class.
- always_confirm: hard-rule short-circuit (rule-engine-first idea).
"""
import argparse
import json
import sys

from common import INIT_CONF, load_policy, THRESHOLD_DEFAULT


def main():
    ap = argparse.ArgumentParser(description="decision-layer decide")
    ap.add_argument("--class", dest="cls", required=True, help="decision class, e.g. persona_assign_research")
    ap.add_argument("--scope", default="", help="authorization / risk scope tag")
    ap.add_argument("--risk", default="low", help="low | med | high")
    ap.add_argument("--candidates", default="[]", help='JSON list [{"id","label","score"}]')
    args = ap.parse_args()

    p = load_policy()
    thr = p.get("threshold", THRESHOLD_DEFAULT)
    conf_map = p.get("confidence", {})
    conf = conf_map.get(args.cls, INIT_CONF)
    is_gap = args.cls not in conf_map  # never decided before -> gap

    risky = (
        (args.scope in p.get("risky_scopes", []))
        or (args.risk == "high")
        or (args.cls in p.get("always_confirm", []))
    )

    try:
        cands = json.loads(args.candidates)
    except Exception:
        cands = []
    rec = max(cands, key=lambda c: float(c.get("score", 0))) if cands else None

    mode = "CONFIRM" if (risky or conf < thr) else "AUTO"
    learned = p.get("preferences", {}).get(args.cls)

    note = "Autonomous decision; will inform the user."
    if risky:
        note = "High-risk / hard-rule: forced CONFIRM."
    elif mode == "CONFIRM":
        note = "Unknown class: needs user confirmation and a stated preference." if is_gap else "Needs user confirmation."

    out = {
        "mode": mode,
        "confidence": round(conf, 3),
        "threshold": thr,
        "risky": risky,
        "is_gap": is_gap,
        "learned_choice": learned,
        "recommended": rec,
        "note": note,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
