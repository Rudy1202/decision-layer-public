#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First-run onboarding for the decision-layer skill.

If policy.json is still the shipped placeholder (user.name == 'your-name' or the
persona field is the default prompt), this collects the user's *name* and a
one-line *persona* describing how they want the agent to reason by default, plus
optional remediation preferences, and persists them to policy.json. After that,
decide.py / correct.py are persona-driven from the very first decision.

This is what makes the skill "persona-driven out of the box" instead of shipping
with an empty template that the user has to hand-edit.

Run modes
---------
  python onboard.py                                   # interactive prompts
  python onboard.py --non-interactive --name X --persona "..."   # agent supplies
  python onboard.py --check                           # exit 0 if onboarded, 1 if default
"""
import argparse
import json
import sys

import common

DEFAULT_NAME = "your-name"
DEFAULT_PERSONA_PREFIX = "Describe how you want"


def is_default(p):
    u = p.get("user", {})
    name = u.get("name")
    persona = str(u.get("persona", ""))
    if name == DEFAULT_NAME:
        return True
    if persona.startswith(DEFAULT_PERSONA_PREFIX):
        return True
    return False


def _prompt(text, default=""):
    try:
        val = input(f"{text} [{default}]: ").strip()
    except EOFError:
        val = ""
    return val or default


def main():
    ap = argparse.ArgumentParser(description="First-run onboarding for decision-layer.")
    ap.add_argument("--name", default=None, help="User display name.")
    ap.add_argument("--persona", default=None,
                    help="One-line description of how the agent should reason by default.")
    ap.add_argument("--background", default=None,
                    help="Optional longer notes about working style / context.")
    ap.add_argument("--non-interactive", action="store_true",
                    help="Do not prompt; use --name/--persona/--background as given.")
    ap.add_argument("--check", action="store_true",
                    help="Exit 0 if already onboarded, 1 if still default (no writes).")
    args = ap.parse_args()

    p = common.load_policy()

    if args.check:
        sys.exit(0 if not is_default(p) else 1)

    # Never clobber an already-onboarded policy in interactive mode.
    if not args.non_interactive and not is_default(p):
        print("policy.json already has a persona; skipping onboarding.")
        print(json.dumps({"onboarded": True, "skipped": True}, ensure_ascii=False))
        return

    if args.non_interactive:
        name = args.name or DEFAULT_NAME
        persona = args.persona or ""
        background = args.background or ""
    else:
        print("First-run setup for decision-layer.")
        print("Press Enter to accept the [default] shown, or type your answer.")
        name = _prompt("Your name", p.get("user", {}).get("name", DEFAULT_NAME))
        persona = _prompt("How should the agent reason by default?", "")
        background = _prompt("Optional background / working-style notes", "")

    p["user"]["name"] = name
    if persona:
        p["user"]["persona"] = persona
    if background:
        p["user"]["background"] = background
    common.save_policy(p)
    print(json.dumps({"onboarded": True, "name": name}, ensure_ascii=False))


if __name__ == "__main__":
    main()
