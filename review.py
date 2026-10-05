#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Review assistant: list pending decisions and apply confirm/override.

Closes the unattended loop:
  scheduled job -> decide_unattended.py appends to decision_log.txt (pending_review)
  -> you review with this tool
  -> confirm/override calls learn.py, raising confidence until the class reaches
     AUTO and drops out of the pending list.

Stdlib only, zero API.
"""
import argparse
import os
import subprocess
import sys

from common import DECISION_LOG, THRESHOLD_DEFAULT, load_policy

LEARN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learn.py")
PY = sys.executable


def parse_log(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            d = {}
            for part in line.split("|"):
                part = part.strip()
                if "=" not in part:
                    continue
                k, v = part.split("=", 1)
                d[k] = v
            rows.append(d)
    return rows


def main():
    ap = argparse.ArgumentParser(description="decision-layer review")
    ap.add_argument("--log", default=DECISION_LOG)
    ap.add_argument("--apply", action="store_true", help="apply a confirm/override")
    ap.add_argument("--class", dest="cls", help="target class")
    ap.add_argument("--outcome", help="confirm | override")
    ap.add_argument("--chosen", default="", help="user's actual chosen id")
    ap.add_argument("--scope", default="", help="optional, for gap_log")
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
        subprocess.run(cmd, check=True)
        return

    p = load_policy()
    thr = p.get("threshold", THRESHOLD_DEFAULT)
    conf = p.get("confidence", {})

    rows = parse_log(args.log)
    latest = {}
    for r in rows:
        latest[r.get("class")] = r

    pending = []
    for cls, r in latest.items():
        if r.get("mode") != "CONFIRM":
            continue
        c = conf.get(cls)
        if c is None or c < thr:
            pending.append((cls, r))

    if not pending:
        print("Nothing pending. Every CONFIRM class has been learned to AUTO, or the log is empty.")
        return

    print(f"{len(pending)} class(es) pending review (still CONFIRM under live policy):\n")
    for cls, r in pending:
        gap = r.get("gap", "N")
        chosen = r.get("chosen", "?")
        print(f"  • class={cls}  gap={gap}  last_chosen={chosen}")
        print(f"      confirm : python review.py --apply --class {cls} --outcome confirm --chosen <id>")
        print(f"      override: python review.py --apply --class {cls} --outcome override --chosen <id>\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
