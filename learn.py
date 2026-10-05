#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Online learning: update confidence + recorded preference from user feedback.

- Always records preferences[class] = the user's actual chosen id
  (pass --chosen <id> on both confirm and override).
- On first resolution of a gap, appends to gap_log for audit.
"""
import argparse
import json
import sys
from datetime import datetime

from common import (
    INIT_CONF, STEP, CAP, BETA, THRESHOLD_DEFAULT, load_policy, save_policy,
)


def main():
    ap = argparse.ArgumentParser(description="decision-layer learn")
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--outcome", required=True, help="confirm | override")
    ap.add_argument("--chosen", default="", help="the user's actual chosen id")
    ap.add_argument("--scope", default="", help="optional, used only for gap_log")
    args = ap.parse_args()

    p = load_policy()
    conf = p.setdefault("confidence", {})
    was_gap = args.cls not in conf
    cur = conf.get(args.cls, INIT_CONF)

    if args.outcome == "confirm":
        new = cur + STEP
    else:  # override
        new = cur * BETA
    new = min(new, CAP)
    conf[args.cls] = round(new, 3)

    if args.chosen:
        p.setdefault("preferences", {})[args.cls] = args.chosen

    if was_gap:
        p.setdefault("gap_log", []).append({
            "class": args.cls,
            "scope": args.scope,
            "resolved_choice": args.chosen,
            "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    thr = p.get("threshold", THRESHOLD_DEFAULT)
    save_policy(p)

    out = {
        "class": args.cls,
        "confidence": conf[args.cls],
        "mode": "AUTO" if conf[args.cls] >= thr else "CONFIRM",
        "was_gap": was_gap,
        "learned_choice": p.get("preferences", {}).get(args.cls),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
