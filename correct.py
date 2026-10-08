#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persona-driven remediation plan generator.

Reads `remediation_style` from policy.json and, given an error description,
outputs a *remediation plan skeleton* ordered by the user's style traits:

  - backup_before_change -> snapshot first (safety gate)
  - plan_before_action   -> write a plan and confirm before editing
  - prefer_direct        -> fix the root cause directly, avoid over-engineering
  - phases                -> ordered stages, e.g. ["quick_fix", "refine"]

The host LLM fills in the concrete steps; this only encodes the *shape* the
user prefers, so the same bug gets a fix that fits the user's taste. Zero-API,
file-only, generic: any agent fixing anything can load the user's
remediation_style and produce a tailored plan.

Example:
  python correct.py --error "ImportError: module 'foo' not found" --class fix_import
  python correct.py --error "..." --json
"""
import argparse
import json
import sys

from common import load_policy


def build_plan(policy, error, cls):
    rs = policy.get("remediation_style", {}) or {}
    phases = rs.get("phases", ["quick_fix", "refine"])
    prefer_direct = rs.get("prefer_direct", True)

    steps = []
    if rs.get("backup_before_change"):
        steps.append({
            "phase": "pre",
            "action": "backup",
            "detail": "Snapshot affected files/config before any change (safety gate: never edit without a rollback).",
        })
    if rs.get("plan_before_action"):
        steps.append({
            "phase": "pre",
            "action": "plan",
            "detail": "Write a short plan of the fix and confirm with the user before editing (esp. for risky scopes).",
        })
    for i, ph in enumerate(phases):
        if prefer_direct:
            detail = (f"Phase {i+1} ({ph}): address the root cause by the most direct route; "
                      "resist incidental refactoring / over-engineering.")
        else:
            detail = f"Phase {i+1} ({ph}): resolve the issue."
        steps.append({"phase": ph, "action": "address", "detail": detail})
    steps.append({
        "phase": "verify",
        "action": "verify",
        "detail": "Verify the fix works; then (if a 'refine' phase exists) evolve it for effectiveness and efficiency.",
    })

    return {
        "error": error,
        "class": cls,
        "style": {
            "prefer_direct": prefer_direct,
            "plan_before_action": rs.get("plan_before_action", True),
            "backup_before_change": rs.get("backup_before_change", True),
            "phases": phases,
        },
        "steps": steps,
    }


def main():
    ap = argparse.ArgumentParser(description="decision-layer remediation planner")
    ap.add_argument("--error", required=True, help="description of the error / issue to fix")
    ap.add_argument("--class", dest="cls", default="", help="optional decision class tag")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    p = load_policy()
    plan = build_plan(p, args.error, args.cls)

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    print(f"Remediation plan for: {args.error}\n")
    for s in plan["steps"]:
        print(f"  [{s['phase']}] {s['action']}: {s['detail']}")
    print("\nStyle in effect:", ", ".join(f"{k}={v}" for k, v in plan["style"].items()))


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
