#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decision-layer — UNATTENDED mode.

Picks the recommended option (argmax of score) and ALWAYS returns it (never
blocks, because nobody is there to confirm). Writes an audit line to the
decision log. Designed for scheduled jobs: even if conf < 0.7 it proceeds,
merely flagging the choice as pending_review.

Enhancements: is_gap / learned_choice / always_confirm short-circuit; log gains
a gap field. The default log lives next to this script; override with --log.
"""
import argparse
import json
import sys
from datetime import datetime

from common import (
    INIT_CONF, THRESHOLD_DEFAULT, DECISION_LOG, load_policy,
)


def main():
    ap = argparse.ArgumentParser(description="decision-layer unattended decide")
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--scope", default="")
    ap.add_argument("--risk", default="low")
    ap.add_argument("--candidates", default="[]", help='JSON [{"id","label","score"}]')
    ap.add_argument("--log", default=DECISION_LOG)
    args = ap.parse_args()

    p = load_policy()
    thr = p.get("threshold", THRESHOLD_DEFAULT)
    conf_map = p.get("confidence", {})
    conf = conf_map.get(args.cls, INIT_CONF)
    is_gap = args.cls not in conf_map
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
    learned = p.get("preferences", {}).get(args.cls)

    mode = "CONFIRM" if (risky or conf < thr) else "AUTO"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    chosen = f"{rec['id']} ({rec['label']})" if rec else "(none)"
    note = "pending_review" if mode == "CONFIRM" else "autonomous"
    line = (f"{ts} | class={args.cls} | scope={args.scope} | risk={args.risk} | "
            f"mode={mode} | conf={round(conf,3)} | chosen={chosen} | gap={'Y' if is_gap else 'N'} | {note}\n")
    try:
        with open(args.log, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        sys.stderr.write(f"[warn] cannot write log: {e}\n")

    out = {
        "chosen_id": rec["id"] if rec else None,
        "label": rec["label"] if rec else None,
        "mode": mode,
        "confidence": round(conf, 3),
        "is_gap": is_gap,
        "learned_choice": learned,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
