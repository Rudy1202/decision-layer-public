---
name: decision-layer
description: >-
  A local, learnable decision layer with no external API. When a reusable
  preference-type decision appears — agent/persona routing, content style, local
  file organization, tool selection — the agent first asks this layer to judge:
  if confidence < 0.7 or the decision is high-risk, it must CONFIRM with the
  user; once confidence >= 0.7 it acts autonomously but still reports the choice.
  Every confirm/override updates confidence online. User background and persona
  live in policy.json (read by the scripts, never injected into the LLM context,
  saving tokens). Includes a Gap Protocol for unknown classes and a review.py
  helper for an unattended review loop.
compatibility: workbuddy, opencode
---

# Decision Layer (local, learnable)

A tiny, dependency-free skill that lets an agent make *reusable* decisions
without burning the user's attention — and without a big agent framework.

## When to use
Use this skill whenever a task contains a **reusable preference-type decision**, e.g.:
- routing work between multiple agents / personas
- choosing content tone / style / format
- local file organization, research routing, tool selection
- anything "we did it last time, we'll probably do it the same way"

**Do not use** for one-off open-ended reasoning (analysis, writing, synthesis) —
hand those straight to the LLM.

## Core principles
1. **Background stays out of the LLM context.** Your persona / background live in
   `policy.json`, read by `decide.py`. The model only needs the verdict + the
   current task + a persona tag — not the whole backstory every turn.
2. **Confidence gate.** Each decision *class* has its own confidence, starting at
   `0.3` (always confirm). A confirm raises it by a fixed `STEP` (`0.3 → 0.5 →
   0.7` ≈ two confirms to reach AUTO); cap `0.95`.
   - `< threshold` or high-risk → `CONFIRM`: show the recommendation, wait.
   - `>= threshold` → `AUTO`: act, then print one `📌 decision: …` line (no block).
3. **Online learning (correction layer).** Confirm → confidence `+= STEP`;
   override → confidence `*= BETA` (trust drops, back to CONFIRM). Either way,
   the user's *actual chosen id* is stored in `preferences[class]`, so next time
   `decide.py` returns `learned_choice`.
4. **Safety gate (never bypassed).** These scopes force CONFIRM at any confidence:
   `external_send`, `delete`, `paid`, `publish`, or `risk=high`. Additionally,
   `policy.json`'s `always_confirm` list can pin specific classes to CONFIRM
   forever (hard-rule short-circuit, highest priority).
5. **Gap Protocol (unknown classes).** If a class was never decided before
   (`confidence` has no entry), `decide.py` flags `is_gap=true`, forces CONFIRM,
   and asks the user to state a preference. The first choice is written to
   `gap_log` for audit; the class then follows the normal confidence curve.

## Workflow
1. Identify the decision: `class`, `scope`, `risk` (low/med/high),
   `candidates` (JSON `[{id,label,score}]`, scored by you during planning).
2. Arbitrate:
   ```
   python decide.py --class <class> --scope <scope> --risk <risk> --candidates '<json>'
   ```
3. If `mode=CONFIRM`: present `recommended`, wait for input, then learn:
   ```
   python learn.py --class <class> --outcome confirm --chosen <chosen id>
   # or, if the user overrides:
   python learn.py --class <class> --outcome override --chosen <chosen id>
   ```
   If `is_gap=true`, this is the class's first appearance — the choice lands in `gap_log`.
4. If `mode=AUTO`: act, and report it with `📌 decision: …`.
5. High-risk / `always_confirm` classes always take the confirm branch.

## Files
- `policy.json` — user background / persona / authorized + risky scopes /
  `always_confirm` hard rules / per-class confidence / learned preferences / `gap_log`.
  *(gitignored; a `policy.example.json` template is shipped instead.)*
- `common.py` — shared constants + policy load/save with first-run auto-create.
- `decide.py` — read policy, output `{mode, confidence, recommended, is_gap, learned_choice, note}`.
- `learn.py` — update `policy.json` confidence + preferences from feedback; logs first gap resolution.
- `decide_unattended.py` — **unattended mode**: same argmax pick, never blocks,
  appends an audit line to `decision_log.txt` (with a `gap=Y/N` field). For scheduled jobs.
- `review.py` — **review helper**: reads `decision_log.txt`, lists classes still
  pending review, supports one-shot `confirm` / `override` (calls `learn.py`).

## Unattended mode (automation / scheduled tasks)
- Call `decide_unattended.py --class <c> --scope <s> --risk low --candidates '<json>'`
  (optionally `--log /path/to/your/log.txt`). It prints `{"chosen_id":...}` and
  **always proceeds with chosen_id — it never waits.**
- Each run appends a line to the decision log (`mode=CONFIRM (pending_review)` or
  `AUTO`, plus `gap=Y/N`).
- Later, review with `python review.py` (lists only still-CONFIRM classes);
  `python review.py --apply --class <c> --outcome confirm --chosen <id>` to confirm,
  or `--outcome override --chosen <id>` to override. Once confidence ≥ threshold
  the class flips to AUTO and drops off the pending list.

## Notes
- This skill is **additive**: it changes no host agent internals. The agent calls
  it only when it judges a decision to be reusable.
- `policy.json` auto-creates from a neutral default on first run; fill in your own
  `user.persona` / `user.background` to taste.
- Confidence is a proxy for "earned trust", not a probability — high scores are not
  a license to skip the safety gate on risky scopes.
