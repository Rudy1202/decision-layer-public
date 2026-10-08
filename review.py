#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review assistant: list pending decisions and apply confirm/override.

Closes the unattended loop:
  scheduled job -> decide_unattended.py appends a JSON line to decision_log.txt
  -> you review with this tool
  -> confirm/override calls learn.py, raising confidence until the class reaches
     AUTO and drops out of the pending list.

Log format: JSONL (one JSON object per line). Legacy pipe-delimited lines are
silently skipped, so an old log keeps working.

Stdlib only, zero API.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

from common import DECISION_LOG, THRESHOLD_DEFAULT, INIT_CONF, STEP, CAP, load_policy

LEARN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learn.py")
PY = sys.executable


def parse_log(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue  # skip legacy text lines
    return rows


def confirms_to_auto(conf, thr):
    """How many more confirms are needed to reach AUTO (capped count)."""
    n = 0
    c = conf
    while c < thr and n < 20:
        c = min(c + STEP, CAP)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="decision-layer review")
    ap.add_argument("--log", default=DECISION_LOG)
    ap.add_argument("--apply", action="store_true", help="apply a confirm/override")
    ap.add_argument("--class", dest="cls", help="target class")
    ap.add_argument("--outcome", help="confirm | override")
    ap.add_argument("--chosen", default="", help="user's actual chosen id")
    ap.add_argument("--scope", default="", help="optional, for gap_log")
    ap.add_argument("--rationale", default="", help="optional why")
    ap.add_argument("--since", default="", help="filter rows with ts >= YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    if args.apply:
        if not args.cls or not args.outcome:
            print("Need --class and --outcome.")
            return
        cmd = [PY, LEARN, "--class", args.cls, "--outcome", args.outcome]
        if args.chosen:
            cmd += ["--chosen", args.chosen]
        if args.scope:
            cmd += ["--scope", args.scope]
        if args.rationale:
            cmd += ["--rationale", args.rationale]
        subprocess.run(cmd, check=True)
        return

    p = load_policy()
    thr = p.get("threshold", THRESHOLD_DEFAULT)
    conf = p.get("confidence", {})

    rows = parse_log(args.log)
    if args.since:
        rows = [r for r in rows if r.get("ts", "") >= args.since]

    latest = {}
    for r in rows:
        latest[r.get("class")] = r

    pending = []
    for cls, r in latest.items():
        if r.get("mode") != "CONFIRM":
            continue
        if r.get("auto_scope"):
            continue
        c = conf.get(cls)
        if c is None or c < thr:
            pending.append((cls, r))

    if not pending:
        msg = "Nothing pending. Every CONFIRM class has been learned to AUTO, or the log is empty."
        print(json.dumps({"pending": []}, ensure_ascii=False) if args.json else msg)
        return

    if args.json:
        out = []
        for cls, r in pending:
            c = conf.get(cls, INIT_CONF)
            out.append({
                "class": cls,
                "gap": r.get("gap", "N"),
                "last_chosen": r.get("chosen"),
                "confidence": c,
                "confirms_to_auto": confirms_to_auto(c, thr),
            })
        print(json.dumps({"pending": out, "threshold": thr}, ensure_ascii=False, indent=2))
        return

    print(f"{len(pending)} class(es) pending review (still CONFIRM under live policy):\n")
    for cls, r in pending:
        c = conf.get(cls, INIT_CONF)
        n = confirms_to_auto(c, thr)
        print(f"  • class={cls}  gap={r.get('gap', 'N')}  last_chosen={r.get('chosen')}  conf={c}  (~{n} confirm(s) to AUTO)")
        print(f"      confirm : python review.py --apply --class {cls} --outcome confirm --chosen <id>")
        print(f"      override: python review.py --apply --class {cls} --outcome override --chosen <id>\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
