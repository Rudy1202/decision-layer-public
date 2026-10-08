# decision-layer

> 📖 中文文档：[README.zh.md](README.zh.md)

A **local, learnable decision layer** for AI coding agents (WorkBuddy / opencode / any
agent that can run a Python script). It lets an agent make *reusable* preference
decisions without pestering you every time — and without a sprawling agent framework.

Zero external APIs. Zero pip dependencies. Pure standard library. Your persona,
learned preferences, and remediation style live in a local JSON file, read by the
scripts, **never injected into the LLM context** (so you save tokens and keep your
backstory private).

---

## Why

Agents face the same small decisions repeatedly: which persona should own this task,
what tone the output should take, how to organize files, which tool to pick, how strict
a code review should be, or — after a bug — what *shape* the fix should take. Two bad
defaults exist today:

- **Always ask** → the agent becomes a nag; you stop reading its prompts.
- **Always guess** → it drifts from your taste and you can't see or steer it.

`decision-layer` sits between them: it **starts by confirming**, watches what you pick,
and **earns autonomy per decision-class**. After ~2 confirmations on a low-risk class it
flips to autonomous — but *still tells you* what it decided, and it can never go
autonomous on risky actions (send / delete / pay / publish).

## Features

- **Confidence gate** — each decision class has its own confidence (start `0.3`,
  `+=0.2` per confirm, cap `0.95`). Below `0.7` → must confirm; at/above → acts and reports.
- **auto_scopes (fast out of the box)** — pre-authorize *safe* classes in `policy.json`
  and they go `AUTO` immediately, so a fresh install feels fast instead of nagging.
- **Online learning** — every confirm/override updates confidence *and* records your
  actual choice (+ optional rationale), so the agent can remind itself ("last time you
  picked `straight`").
- **Gap Protocol** — an *unknown* class is force-confirmed on first sight and its
  resolution is audit-logged, then follows the normal curve.
- **Hard rules** — `always_confirm` list and risky scopes (`external_send`, `delete`,
  `paid`, `publish`, `risk=high`) override confidence and force a confirm. `auto_scopes`
  can never bypass this.
- **Freshness decay** — classes untouched in `decay_days` (default 30) lose confidence,
  so stale preferences fall back to review.
- **Unattended mode** — for scheduled jobs: picks the best option, never blocks, and
  writes a JSONL audit log you review later with one command.
- **Review helper** — `review.py` lists only the classes still pending your check
  (`--json`, `--since`), and applies confirm/override in one shot.
- **Persona-driven remediation** — `correct.py` turns an error into a fix-plan skeleton
  shaped by your `remediation_style` (backup first, plan before action, prefer direct,
  ordered phases).

## How it works

```
            ┌─────────────┐
 you ──────►│ decide.py   │  class + candidates + risk
            └──────┬──────┘
                   │ reads policy.json (persona + confidence)
                   ▼
          ┌────────────────┐
          │  CONFIRM ?     │  conf<thr OR risky OR always_confirm OR is_gap
          │  (auto_scope → AUTO, risky → CONFIRM)
          └───┬───────┬────┘
         yes  │       │ no
              ▼       ▼
        ask you    act + 📌 report
              │
        you pick → learn.py  (conf += STEP, store choice + rationale)
              │
              ▼  (repeat until conf ≥ 0.7, or pre-authorized via auto_scopes)
           AUTO next time
```

Learning model (in `common.py`, all tunable):

| Event | Confidence update |
|---|---|
| first seen (gap) | `0.3` |
| confirm | `min(conf + 0.2, 0.95)` |
| override | `conf * 0.5` |
| untouched `decay_days` | `max(0.3, conf * 0.7)` |

## Install

The skill is just a folder of `.py` files. Drop it where your agent looks for skills:

**WorkBuddy**
```
~/.workbuddy/skills/decision-layer/   ← copy this folder here
```

**opencode**
```
~/.config/opencode/skills/decision-layer/   ← copy this folder here
```

**Any agent / plain Python**
```
git clone https://github.com/<you>/decision-layer.git
cd decision-layer
# that's it — no build, no pip
```

### Requirements / dependencies

- **Python 3.8+** (uses only the standard library: `argparse`, `json`, `os`, `sys`,
  `datetime`, `subprocess`).
- **No third-party packages.** There is no `pip install` step. A `requirements.txt`
  documents this; it intentionally lists nothing to install.

> On first run `policy.json` is auto-created from a neutral default. Edit
> `policy.json → user.persona` / `user.background` / `remediation_style` to describe
> how you like to work, and add safe classes to `auto_scopes` for instant autonomy.

## Quick start

```bash
# 1. Arbitrate a decision
python decide.py --class news_angle --scope content_style --risk low \
  --candidates '[{"id":"straight","label":"Straight news","score":0.8},{"id":"context","label":"With context","score":0.5}]'

# 2. It says CONFIRM (first time). You pick "straight":
python learn.py --class news_angle --outcome confirm --chosen straight --rationale "Keep it concise"

# 3. Run again — still CONFIRM until conf reaches 0.7 (≈2 confirms), then AUTO.
python decide.py --class news_angle --scope content_style --risk low \
  --candidates '[{"id":"straight","label":"Straight news","score":0.8}]'
```

### Pre-authorize safe classes (go fast immediately)

Edit `policy.json`:
```json
"auto_scopes": ["news_angle", "bible_tone", "yt_selection"]
```
Now those low-risk classes return `AUTO` on the very first call — no warm-up nagging.

### Unattended / scheduled

```bash
# In a cron / automation, never blocks:
python decide_unattended.py --class yt_selection --scope content_style --risk low \
  --candidates '[{"id":"recent_top","label":"Recent top","score":0.7}]' \
  --log /path/to/decision_log.txt

# Later, review what it decided:
python review.py --log /path/to/decision_log.txt
python review.py --apply --class yt_selection --outcome confirm --chosen recent_top
```

### Persona-driven remediation

```bash
python correct.py --error "ImportError: cannot import name 'X' from 'Y'" --class fix_import
# prints a plan skeleton honoring your remediation_style (backup -> plan -> phases -> verify)
```

## Using it for code building / review

The skill is generic; "code" is just more decision classes. Suggested classes
(document them in your `policy.json` — they appear automatically on first use):

| Decision class | Example candidates |
|---|---|
| `code_review_strictness` | `security_only` vs `full_style` |
| `refactor_aggressiveness` | `minimal` vs `restructure` |
| `test_strategy` | `happy_path` vs `edge_cases` vs `mutation` |
| `error_handling_policy` | `fail_fast` vs `graceful_degrade` |
| `fix_vs_report` | `apply_fix` vs `report_only` |

Wire it into your agent's plan/build/review step: before acting, call `decide.py`
with the candidate approaches; if it returns `AUTO`, proceed; if `CONFIRM`, show the
recommendation. After an error, call `correct.py` to shape the fix to the user's taste.

## Configuration (`policy.json`)

| Key | Meaning |
|---|---|
| `user.name` / `user.persona` / `user.background` | your profile, read by scripts, kept out of LLM context |
| `threshold` | confidence at/above which a class goes AUTO (default `0.7`) |
| `authorized_scopes` | scopes the agent may handle (informational) |
| `risky_scopes` | scopes that always force CONFIRM (`external_send`, `delete`, `paid`, `publish`) |
| `always_confirm` | classes pinned to CONFIRM forever (highest priority) |
| `auto_scopes` | pre-authorized SAFE classes → AUTO from install (never blocks) |
| `confidence` / `last_seen` | per-class learned confidence + freshness (managed by learn.py) |
| `preferences` | per-class last chosen id + rationale (managed by learn.py) |
| `gap_log` | audit of first-time resolutions for unknown classes |
| `remediation_style` | persona traits used by `correct.py` (phases, prefer_direct, plan_before_action, backup_before_change) |
| `decay_days` | days of inactivity before a class's confidence decays (0 = disable) |

## Privacy & safety

- **No network.** Everything is local files. No telemetry, no API keys.
- **No LLM-in-the-loop for the decision.** The verdict is pure file + math, so the
  agent's reasoning stays cheap and deterministic.
- **Risky actions can't go autonomous.** Send/delete/pay/publish always require you,
  and `auto_scopes` can't override that.
- **You stay in control.** Confidence is "earned trust", not probability; the safety
  gate ignores it.

## Related projects

This skill is small on purpose and stands on the shoulders of a few public ideas
(acknowledged, not copied):

- **[selinayfilizp/decision](https://github.com/selinayfilizp/decision)** — the
  `DECISION.md` "judgment layer" + Gap Protocol pattern inspired the unknown-class flow.
- **dot-skill / colleague-skill** — the *correction layer* idea (record the user's real
  choice and reuse it) inspired `preferences[class]`.
- **GitHub Issues Agent confidence gating** — the threshold→autonomous / reason-audit
  pattern.
- **Jev decision layer** — a different, token-ROI / multi-key approach we explicitly
  *did not* follow, to keep this dependency-free.

What's distinctive here: the combination of **per-class confidence learning + auto_scopes
fast-start + an unattended JSONL review loop + persona-driven remediation**, packaged as
a drop-in skill with no runtime dependencies.

## License

MIT — see [LICENSE](LICENSE).
