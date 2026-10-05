#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for the decision-layer skill.

- Resolves policy.json relative to this folder.
- Auto-creates a default policy on first run so the skill works out of the box.
- Single source of tuning constants (threshold, init confidence, learning rate).
"""
import json
import os

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
POLICY = os.path.join(SKILL_DIR, "policy.json")
DECISION_LOG = os.path.join(SKILL_DIR, "decision_log.txt")  # default audit log; override with --log

# --- Tunable constants -------------------------------------------------------
THRESHOLD_DEFAULT = 0.7   # confidence >= threshold -> AUTO
INIT_CONF = 0.3           # first-seen class starts here (always CONFIRM)
STEP = 0.2                # confirm raises confidence by this fixed amount
CAP = 0.95                # confidence ceiling (stay a little humble)
BETA = 0.5                # override multiplies confidence by this (trust drop)
# ----------------------------------------------------------------------------

DEFAULT_POLICY = {
    "user": {
        "name": "your-name",
        "persona": "Describe how you want the agent to reason by default, e.g. "
                   "'Prefer the simplest solution that works; think straight, no over-engineering.'",
        "background": "Optional longer notes about your working style, project context, or recurring preferences."
    },
    "threshold": THRESHOLD_DEFAULT,
    "authorized_scopes": [
        "persona_assignment",
        "content_style",
        "local_file_organize",
        "research_routing",
        "tool_selection"
    ],
    "risky_scopes": [
        "external_send",
        "delete",
        "paid",
        "publish"
    ],
    "always_confirm": [],
    "confidence": {},
    "preferences": {},
    "gap_log": []
}


def load_policy():
    if not os.path.exists(POLICY):
        save_policy(DEFAULT_POLICY)
    with open(POLICY, encoding="utf-8") as f:
        return json.load(f)


def save_policy(p):
    with open(POLICY, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)
