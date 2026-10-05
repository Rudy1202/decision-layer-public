# decision-layer

A **local, learnable decision layer** for AI coding agents (WorkBuddy / opencode / any
agent that can run a Python script). It lets an agent make *reusable* preference
decisions without pestering you every time — and without a sprawling agent framework.

Zero external APIs. Zero pip dependencies. Pure standard library. Your persona and
learned preferences live in a local JSON file, read by the scripts, **never injected
into the LLM context** (so you save tokens and keep your backstory private).

---

## Why

Agents face the same small decisions repeatedly: which persona should own this task,
what tone the output should take, how to organize files, which tool to pick. Two bad
defaults exist today:

- **Always ask** → the agent becomes a nag; you stop reading its prompts.
- **Always guess** → it drifts from your taste and you can't see or steer it.

`decision-layer` sits between them: it **starts by confirming**, watches what you
pick, and **earns autonomy per decision-class**. After ~2 confirmations on a low-risk
class it flips to autonomous — but *still tells you* what it decided, and it can never
go autonomous on risky actions (send / delete / pay / publish).

## Features

- **Confidence gate** — each decision class has its own confidence (start `0.3`,
  `+=0.2` per confirm, cap `0.95`). Below `0.7` → must confirm; at/above → acts and
  reports.
- **Online learning** — every confirm/override updates confidence *and* records your
  actual choice, so the agent can remind itself ("last time you picked `straight`").
- **Gap Protocol** — an *unknown* class is force-confirmed on first sight and its
  resolution is audit-logged, then follows the normal curve.
- **Hard rules** — `always_confirm` list and risky scopes (`external_send`, `delete`,
  `paid`, `publish`, `risk=high`) override confidence and force a confirm.
- **Unattended mode** — for scheduled jobs: picks the best option, never blocks, and
  writes an audit log you review later with one command.
- **Review helper** — `review.py` lists only the classes still pending your check and
  applies confirm/override in one shot.

## How it works

```
            ┌─────────────┐
 you ──────►│ decide.py   │  class + candidates + risk
            └──────┬──────┘
                   │ reads policy.json (persona + confidence)
                   ▼
          ┌────────────────┐
          │  CONFIRM ?     │  conf<thr OR risky OR always_confirm OR is_gap
          └───┬───────┬────┘
         yes  │       │ no
              ▼       ▼
        ask you    act + 📌 report
              │
        you pick → learn.py  (conf += STEP, store choice)
              │
              ▼  (repeat until conf ≥ 0.7)
           AUTO next time
```

Learning model (in `common.py`, all tunable):

| Event | Confidence update |
|---|---|
| first seen (gap) | `0.3` |
| confirm | `min(conf + 0.2, 0.95)` |
| override | `conf * 0.5` |

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

Requires Python 3.8+. No `pip install` needed.

> On first run `policy.json` is auto-created from a neutral default. Edit
> `policy.json → user.persona` / `user.background` to describe how you like to work.

## Quick start

```bash
# 1. Arbitrate a decision
python decide.py --class news_angle --scope content_style --risk low \
  --candidates '[{"id":"straight","label":"Straight news","score":0.8},{"id":"context","label":"With context","score":0.5}]'

# 2. It says CONFIRM (first time). You pick "straight":
python learn.py --class news_angle --outcome confirm --chosen straight

# 3. Run again — still CONFIRM until conf reaches 0.7 (≈2 confirms), then AUTO.
python decide.py --class news_angle --scope content_style --risk low \
  --candidates '[{"id":"straight","label":"Straight news","score":0.8}]'
```

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

## Configuration (`policy.json`)

| Key | Meaning |
|---|---|
| `user.name` / `user.persona` / `user.background` | your profile, read by scripts, kept out of LLM context |
| `threshold` | confidence at/above which a class goes AUTO (default `0.7`) |
| `authorized_scopes` | scopes the agent may handle (informational) |
| `risky_scopes` | scopes that always force CONFIRM (`external_send`, `delete`, `paid`, `publish`) |
| `always_confirm` | classes pinned to CONFIRM forever (highest priority) |
| `confidence` | per-class learned confidence (managed by `learn.py`) |
| `preferences` | per-class last chosen id (managed by `learn.py`) |
| `gap_log` | audit of first-time resolutions for unknown classes |

## Privacy & safety

- **No network.** Everything is local files. No telemetry, no API keys.
- **No LLM-in-the-loop for the decision.** The verdict is pure file + math, so the
  agent's reasoning stays cheap and deterministic.
- **Risky actions can't go autonomous.** Send/delete/pay/publish always require you.
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

What's distinctive here: the combination of **per-class confidence learning + an
unattended review loop + a hard safety gate**, packaged as a drop-in skill with no
runtime dependencies.

## License

MIT — see [LICENSE](LICENSE).
