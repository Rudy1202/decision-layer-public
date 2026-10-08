#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared helpers for the decision-layer skill.

- Resolves policy.json relative to this folder.
- Auto-creates a default policy on first run so the skill works out of the box.
- Single source of tuning constants (threshold, init confidence, learning rate).
- Holds the learnable state schema: confidence, last_seen, preferences,
  auto_scopes, and remediation_style.
"""
import json
import os
from datetime import date, datetime

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
POLICY = os.path.join(SKILL_DIR, "policy.json")
DECISION_LOG = os.path.join(SKILL_DIR, "decision_log.txt")  # default audit log; override with --log

# --- Tunable constants -------------------------------------------------------
THRESHOLD_DEFAULT = 0.7   # confidence >= threshold -> AUTO
INIT_CONF = 0.3           # first-seen class starts here (always CONFIRM)
STEP = 0.2                # confirm raises confidence by this fixed amount
CAP = 0.95                # confidence ceiling (stay a little humble)
BETA = 0.5                # override multiplies confidence by this (trust drop)
DECAY_DAYS = 30          # a class untouched this long decays
DECAY_FACTOR = 0.7       # decay multiplier (floor = INIT_CONF)
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
        "tool_selection",
        "code_review",
        "refactor",
        "test_strategy"
    ],
    "risky_scopes": [
        "external_send",
        "delete",
        "paid",
        "publish"
    ],
    "always_confirm": [],
    "auto_scopes": [],       # pre-authorized SAFE classes -> AUTO from install (never blocks)
    "confidence": {},        # class -> learned confidence (managed by learn.py)
    "last_seen": {},         # class -> YYYY-MM-DD, freshness tracking for decay
    "preferences": {},       # class -> {"chosen": id, "rationale": "..."} (managed by learn.py)
    "gap_log": [],           # audit of first-time resolutions for unknown classes
    "remediation_style": {   # persona-driven correction shape (used by correct.py)
        "phases": ["quick_fix", "refine"],
        "prefer_direct": True,
        "plan_before_action": True,
        "backup_before_change": True,
        "notes": "Optional: how you like fixes delivered."
    },
    "decay_days": DECAY_DAYS
}


def load_policy():
    if not os.path.exists(POLICY):
        save_policy(DEFAULT_POLICY)
    with open(POLICY, encoding="utf-8") as f:
        return json.load(f)


def save_policy(p):
    with open(POLICY, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def apply_decay(p):
    """Decay confidence for classes not seen in decay_days. No-op if decay_days<=0."""
    dd = p.get("decay_days", DECAY_DAYS)
    if not dd:
        return
    today = date.today()
    conf = p.setdefault("confidence", {})
    seen = p.setdefault("last_seen", {})
    for cls, ts in list(seen.items()):
        try:
            d = datetime.strptime(ts, "%Y-%m-%d").date()
        except Exception:
            continue
        if (today - d).days > dd:
            conf[cls] = round(max(INIT_CONF, conf.get(cls, INIT_CONF) * DECAY_FACTOR), 3)


def touch(cls, p):
    p.setdefault("last_seen", {})[cls] = date.today().strftime("%Y-%m-%d")


def learned_choice_of(p, cls):
    """Return (chosen_id, rationale) for a class, handling both dict and legacy string form."""
    v = p.get("preferences", {}).get(cls)
    if isinstance(v, dict):
        return v.get("chosen"), v.get("rationale")
    return v, None
