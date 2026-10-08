#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decision-layer — UNATTENDED mode.

Picks the recommended option (argmax of score) and ALWAYS returns it (never
blocks, because nobody is there to confirm). Appends one JSON line to the
decision log (JSONL) so any host — agent, cron, or review tool — can parse it
programmatically. Designed for scheduled jobs.

Enhancements: is_gap / learned_choice / always_confirm / auto_scope; the log is
now JSONL (one JSON object per line). The default log lives next to this script;
override with --log.
"""
import argparse
import json
import sys
from datetime import datetime

from common import (
    INIT_CONF, THRESHOLD_DEFAULT, DECISION_LOG,
    load_policy, save_policy, apply_decay, touch, learned_choice_of,
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
    apply_decay(p)
    thr = p.get("threshold", THRESHOLD_DEFAULT)
    conf_map = p.get("confidence", {})
    conf = conf_map.get(args.cls, INIT_CONF)
    is_gap = args.cls not in conf_map
    risky = (
        (args.scope in p.get("risky_scopes", []))
        or (args.risk == "high")
        or (args.cls in p.get("always_confirm", []))
    )
    auto_scope = (args.cls in p.get("auto_scopes", [])) and not risky

    try:
        cands = json.loads(args.candidates)
    except Exception:
        cands = []
    rec = max(cands, key=lambda c: float(c.get("score", 0))) if cands else None
    learned, rationale = learned_choice_of(p, args.cls)

    mode = "AUTO" if (auto_scope or (not risky and conf >= thr)) else "CONFIRM"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chosen = f"{rec['id']} ({rec['label']})" if rec else "(none)"
    note = "pending_review" if mode == "CONFIRM" else "autonomous"
    entry = {
        "ts": ts,
        "class": args.cls,
        "scope": args.scope,
        "risk": args.risk,
        "mode": mode,
        "conf": round(conf, 3),
        "chosen": chosen,
        "chosen_id": rec["id"] if rec else None,
        "is_gap": is_gap,
        "auto_scope": auto_scope,
        "gap": "Y" if is_gap else "N",
        "note": note,
    }
    try:
        with open(args.log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        sys.stderr.write(f"[warn] cannot write log: {e}\n")

    touch(args.cls, p)
    save_policy(p)

    out = {
        "chosen_id": rec["id"] if rec else None,
        "label": rec["label"] if rec else None,
        "mode": mode,
        "confidence": round(conf, 3),
        "is_gap": is_gap,
        "auto_scope": auto_scope,
        "learned_choice": learned,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
