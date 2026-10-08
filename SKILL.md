---
name: decision-layer
description: >-
  A local, learnable decision layer with no external API. When a reusable
  preference-type decision appears — agent/persona routing, content style, local
  file organization, tool selection, code-review strictness, or a fix strategy —
  the agent first asks this layer to judge: if confidence < 0.7 or the decision
  is high-risk, it must CONFIRM with the user; once confidence >= 0.7 (or the
  class is pre-authorized via auto_scopes) it acts autonomously but still reports
  the choice. Every confirm/override updates confidence online. User background,
  persona, and remediation style live in policy.json (read by the scripts, never
  injected into the LLM context, saving tokens). Includes a Gap Protocol for
  unknown classes, a review.py helper for an unattended review loop, and
  correct.py for persona-driven remediation plans.
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
- **code building / review**: review strictness, refactor aggressiveness, test strategy, error-handling policy, framework choice, fix-vs-report
- **remediation**: after an error is found, shape the fix plan to the user's taste
- anything "we did it last time, we'll probably do it the same way"

**Do not use** for one-off open-ended reasoning (analysis, writing, synthesis) —
hand those straight to the LLM.

## Core principles
1. **Background stays out of the LLM context.** Your persona / background /
   remediation_style live in `policy.json`, read by the scripts. The model only
   needs the verdict + the current task + a persona tag — not the whole backstory.
2. **Confidence gate.** Each decision *class* has its own confidence, starting at
   `0.3` (always confirm). A confirm raises it by a fixed `STEP` (`0.3 → 0.5 →
   `0.7` ≈ two confirms to reach AUTO); cap `0.95`.
   - `< threshold` or high-risk → `CONFIRM`: show the recommendation, wait.
   - `>= threshold` → `AUTO`: act, then print one `📌 decision: …` line (no block).
3. **auto_scopes (fast out of the box).** List *pre-authorized, safe* classes in
   `policy.json → auto_scopes`; they go `AUTO` immediately, no waiting. This is the
   lever that makes a fresh install feel fast instead of nagging. Risky classes can
   never be auto_scopes (the safety gate always wins).
4. **Online learning (correction layer).** Confirm → confidence `+= STEP`;
   override → confidence `*= BETA` (trust drops, back to CONFIRM). Either way, the
   user's *actual chosen id* (and optional rationale) is stored in
   `preferences[class]`, so next time `decide.py` returns `learned_choice`.
5. **Safety gate (never bypassed).** These scopes force CONFIRM at any confidence:
   `external_send`, `delete`, `paid`, `publish`, or `risk=high`. Additionally,
   `policy.json`'s `always_confirm` list can pin specific classes to CONFIRM
   forever (hard-rule short-circuit, highest priority). `auto_scopes` cannot
   override this.
6. **Gap Protocol (unknown classes).** If a class was never decided before
   (`confidence` has no entry), `decide.py` flags `is_gap=true`, forces CONFIRM,
   and asks the user to state a preference. The first choice is written to
   `gap_log` for audit; the class then follows the normal confidence curve.
7. **Freshness (decay).** Classes not touched in `decay_days` (default 30) have
   their confidence multiplied by `0.7` (floor `INIT_CONF`), so stale preferences
   fall back to review instead of going stale-autonomous. Set `decay_days: 0` to disable.

## First-run onboarding (persona capture)
This skill is *persona-driven*, so before the first real decision the agent should
make sure `policy.json` has the user's persona. Detection + capture:

1. Run `python onboard.py --check`. If it exits `0`, the user is already onboarded — skip.
2. If it exits `1` (policy is still the shipped placeholder), capture the persona:
   - **Preferred:** ask the user in natural language for their name and a one-line
     description of how they want the agent to reason by default (and optionally
     their working-style background), then persist it:
     ```
     python onboard.py --non-interactive --name "<name>" --persona "<one line>" --background "<opt>"
     ```
   - **Or** let the user run `python onboard.py` interactively at a terminal.
3. After onboarding, `decide.py` / `correct.py` read the persona automatically.
   The persona lives in `policy.json` and is **never injected into the LLM context**
   — the agent only needs the verdict + a persona tag, saving tokens.

Note: onboarding is a one-time setup, not a per-decision prompt. Once captured, it
is never asked again (and `onboard.py` refuses to clobber an existing persona).

## Workflow
1. Identify the decision: `class`, `scope`, `risk` (low/med/high),
   `candidates` (JSON `[{id,label,score}]`, scored by you during planning).
2. Arbitrate:
   ```
   python decide.py --class <class> --scope <scope> --risk <risk> --candidates '<json>'
   ```
3. If `mode=CONFIRM`: present `recommended`, wait for input, then learn:
   ```
   python learn.py --class <class> --outcome confirm --chosen <chosen id> --rationale "<why>"
   # or, if the user overrides:
   python learn.py --class <class> --outcome override --chosen <chosen id>
   ```
   If `is_gap=true`, this is the class's first appearance — the choice lands in `gap_log`.
4. If `mode=AUTO` (or `auto_scope=true`): act, and report it with `📌 decision: …`.
5. High-risk / `always_confirm` / non-auto_scope classes always take the confirm branch.

## Files
- `policy.json` — user background / persona / authorized + risky scopes / `always_confirm`
  hard rules / `auto_scopes` pre-auth / per-class confidence + `last_seen` / learned
  `preferences` (+ rationale) / `gap_log` / `remediation_style`.
  *(gitignored; a `policy.example.json` template is shipped instead.)*
- `common.py` — shared constants + policy load/save with first-run auto-create.
- `decide.py` — read policy, output `{mode, confidence, recommended, is_gap, auto_scope, learned_choice, rationale, note}`.
- `learn.py` — update `policy.json` confidence + preferences (with rationale) from feedback; logs first gap resolution; applies decay.
- `decide_unattended.py` — **unattended mode**: same argmax pick, never blocks, appends a
  JSON line (JSONL) to `decision_log.txt` (with `gap`/`auto_scope` fields). For scheduled jobs.
- `review.py` — **review helper**: reads the JSONL log, lists classes still pending review
  (`--json` machine output, `--since YYYY-MM-DD` filter, shows confirms-to-AUTO preview),
  supports one-shot `confirm` / `override` (calls `learn.py`).
- `correct.py` — **remediation planner**: reads `remediation_style`, turns an error
  description into a persona-shaped fix-plan skeleton (backup → plan → phases → verify).

## Unattended mode (automation / scheduled tasks)
- Call `decide_unattended.py --class <c> --scope <s> --risk low --candidates '<json>'`
  (optionally `--log /path/to/your/log.txt`). It prints `{"chosen_id":...}` and
  **always proceeds with chosen_id — it never waits.**
- Each run appends a JSON line to the decision log (`mode=CONFIRM (pending_review)` or
  `AUTO`, plus `gap`/`auto_scope`).
- Later, review with `python review.py` (lists only still-CONFIRM classes);
  `python review.py --apply --class <c> --outcome confirm --chosen <id>` to confirm,
  or `--outcome override --chosen <id>` to override. Once confidence ≥ threshold the
  class flips to AUTO and drops off the pending list. Old pipe-delimited log lines are
  skipped automatically.

## Remediation (`correct.py`) — persona-driven fixes
After you (the agent) find an error, instead of guessing a generic fix, run:
```
python correct.py --error "ImportError: cannot import name 'X' from 'Y'" --class fix_import
```
It reads `remediation_style` and prints a plan skeleton honoring the user's traits
(backup first, plan before action, prefer direct, ordered phases). You (the LLM) then
fill in the concrete steps. This makes the *same* bug get a fix that fits the user's taste.

## Notes
- This skill is **additive**: it changes no host agent internals. The agent calls it
  only when it judges a decision to be reusable.
- `policy.json` auto-creates from a neutral default on first run; fill in your own
  `user.persona` / `user.background` / `remediation_style` to taste.
- Confidence is a proxy for "earned trust", not a probability — high scores are not a
  license to skip the safety gate on risky scopes.
