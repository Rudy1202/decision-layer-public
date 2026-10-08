# decision-layer（决策层）

一个**本地、可学习的决策层**技能，适用于各类 AI 编码智能体（WorkBuddy / opencode / 任何能跑 Python 脚本的智能体）。它让智能体对**可复用的偏好型决策**做出判断，既不每次都打扰你，也不需要笨重的智能体框架。

零外部 API。零 pip 依赖。纯标准库。你的 persona、学到的偏好、以及改正风格都存在本地 JSON 文件里，由脚本读取，**绝不注入 LLM 上下文**（省 token、保隐私）。

---

## 为什么需要它

智能体总会反复遇到同样的小决策：这个任务交给哪个 persona？输出用什么语气？文件怎么归类？选哪个工具？代码审查要多严格？或者——找到 bug 后，**修复方案该长什么样**？目前只有两种糟糕的默认：

- **永远问** → 智能体变成"碎碎念"，你最后懒得看它的提示。
- **永远猜** → 它慢慢偏离你的口味，而你既看不见也无法纠正。

`decision-layer` 站在中间：**先确认，观察你选什么，然后按决策类逐步赢得自主权**。一个低风险类大约确认 2 次后就转自主——但**仍会告诉你**它做了什么，并且对任何危险动作（发送 / 删除 / 付费 / 发布）永远无法自主。

## 特性

- **置信度门控** — 每个决策类有独立置信度（起始 `0.3`，每次确认 `+0.2`，上限 `0.95`）。低于 `0.7` → 必须确认；达到 → 自行执行并汇报。
- **auto_scopes（装上即快）** — 在 `policy.json` 里预授权**安全**类，它们首次调用就直接 `AUTO`，新手立刻快起来，不再"每次都问"。
- **在线学习** — 每次确认/推翻都会更新置信度，并**记录你真实的选择（+可选理由）**，下次 `decide.py` 会回显 `learned_choice`（"上次你选了 `straight`"）。
- **Gap Protocol（未知决策类）** — 从未出现过的类首次会被强制确认，并把这次选择写进审计日志 `gap_log`，之后走正常曲线。
- **硬规则** — `always_confirm` 列表与危险范围（`external_send`、`delete`、`paid`、`publish`、`risk=high`）无视置信度、强制确认；`auto_scopes` 无法绕过它。
- **新鲜度衰减** — 超过 `decay_days`（默认 30 天）没碰的类，置信度会衰减，避免偏好过时却仍"自主"。
- **无人值守模式** — 给定时任务用：选出最优项、永不阻塞，并把审计日志写成 JSONL，事后一条命令复核。
- **复核助手** — `review.py` 只列出仍需你复核的类（`--json`、`--since`），一键 `confirm` / `override`。
- **按 persona 驱动改正** — `correct.py` 把一段错误描述，按你的 `remediation_style` 生成"改正计划骨架"（先备份、先计划、走直路、分阶段）。

## 工作原理

```
            ┌─────────────┐
 你 ──────►│ decide.py   │  class + candidates + risk
            └──────┬──────┘
                   │ 读取 policy.json（persona + 置信度）
                   ▼
          ┌────────────────┐
          │  要确认吗？     │  conf<thr 或 危险 或 always_confirm 或 is_gap
          │  (auto_scope → AUTO, 危险 → CONFIRM)
          └───┬───────┬────┘
        是 │       │ 否
              ▼       ▼
         问你      执行 + 📌 汇报
              │
        你选择 → learn.py  （置信度 += STEP，记录选择 + 理由）
              │
              ▼  （重复直到 conf ≥ 0.7，或经 auto_scopes 预授权）
          下次转 AUTO
```

学习模型（都在 `common.py` 里，可调）：

| 事件 | 置信度更新 |
|---|---|
| 首次出现（gap） | `0.3` |
| 确认 | `min(conf + 0.2, 0.95)` |
| 推翻 | `conf * 0.5` |
| 超过 decay_days 未碰 | `max(0.3, conf * 0.7)` |

## 安装

本技能就是一个装着 `.py` 文件的文件夹。把它放到你的智能体寻找技能的位置即可：

**WorkBuddy**
```
~/.workbuddy/skills/decision-layer/   ← 把本文件夹复制到这里
```

**opencode**
```
~/.config/opencode/skills/decision-layer/   ← 把本文件夹复制到这里
```

**任何智能体 / 纯 Python**
```
git clone https://github.com/<你>/decision-layer.git
cd decision-layer
# 就这样——无需构建，无需 pip
```

### 运行环境与依赖

- **Python 3.8+**（只用标准库：`argparse`、`json`、`os`、`sys`、`datetime`、`subprocess`）。
- **无任何第三方包。** 没有 `pip install` 步骤。`requirements.txt` 说明了这一点，里面刻意不列任何需安装的包。

> 首次运行会基于中性默认值自动生成 `policy.json`。跑一次 `python onboard.py` 记录你的名字与 persona（或由智能体代你录入），再可选地把安全类加进 `auto_scopes` 即可立即获得自主权。你也可以直接手改 `policy.json → user.persona` / `user.background` / `remediation_style`。

## 快速开始

```bash
# 1. 裁决一个决策
python decide.py --class news_angle --scope content_style --risk low \
  --candidates '[{"id":"straight","label":"直述","score":0.8},{"id":"context","label":"带背景","score":0.5}]'

# 2. 它返回 CONFIRM（第一次）。你选 "straight"：
python learn.py --class news_angle --outcome confirm --chosen straight --rationale "保持简洁"

# 3. 再跑一次——在 conf 到 0.7 之前仍是 CONFIRM，之后转 AUTO。
python decide.py --class news_angle --scope content_style --risk low \
  --candidates '[{"id":"straight","label":"直述","score":0.8}]'
```

### 首启引导（记录你的 persona）

技能是 **persona 驱动** 的，所以在第一次真正决策前先记录你的风格。两种方式：

```bash
# 交互式（在终端）：
python onboard.py
#   Your name [your-name]: Wongr
#   How should the agent reason by default?: 偏好最简单可行的方案；直截了当，不过度设计。
#   Optional background / working-style notes: 先快后精。

# 或智能体代录（智能体问完后替你跑）：
python onboard.py --non-interactive --name "Wongr" \
  --persona "Prefer the simplest solution; think straight, no over-engineering." \
  --background "Fast first, refine later."
```

录入后 `decide.py` / `correct.py` 会自动读取你的 persona，且**不会再被追问**。`onboard.py --check` 在已录入时退出码为 `0`（智能体可据此判断状态）。persona 存在 `policy.json` 里，**永不注入 LLM 上下文**——智能体只需裁决结果加一个 persona 标签，省 token。

### 预授权安全类（立即变快）

编辑 `policy.json`：
```json
"auto_scopes": ["news_angle", "bible_tone", "yt_selection"]
```
这些低风险类首次调用就返回 `AUTO`——无需"热身"追问。

### 无人值守 / 定时任务

```bash
# 在 cron / 自动化里调用，永不阻塞：
python decide_unattended.py --class yt_selection --scope content_style --risk low \
  --candidates '[{"id":"recent_top","label":"近期热门","score":0.7}]' \
  --log /path/to/decision_log.txt

# 之后复核它做了什么：
python review.py --log /path/to/decision_log.txt
python review.py --apply --class yt_selection --outcome confirm --chosen recent_top
```

### 按 persona 驱动改正

```bash
python correct.py --error "ImportError: cannot import name 'X' from 'Y'" --class fix_import
# 打印一份按你 remediation_style 生成的改正计划骨架（备份 -> 计划 -> 分阶段 -> 验证）
```

## 用于代码建立 / 审查

技能本身通用；"代码"只是更多决策类。建议在 `policy.json` 里登记这些类（首次使用会自动出现）：

| 决策类 | 候选例子 |
|---|---|
| `code_review_strictness` | `security_only` vs `full_style` |
| `refactor_aggressiveness` | `minimal` vs `restructure` |
| `test_strategy` | `happy_path` vs `edge_cases` vs `mutation` |
| `error_handling_policy` | `fail_fast` vs `graceful_degrade` |
| `fix_vs_report` | `apply_fix` vs `report_only` |

把它接进智能体的 plan/build/review 步骤：动手前先用候选方案调 `decide.py`；返回 `AUTO` 就执行，返回 `CONFIRM` 就展示推荐。找到错误后调 `correct.py`，让修复方案贴合用户口味。

## 配置（`policy.json`）

| 字段 | 含义 |
|---|---|
| `user.name` / `user.persona` / `user.background` | 你的画像，由脚本读取，不进 LLM 上下文 |
| `threshold` | 达到该置信度即转 AUTO（默认 `0.7`） |
| `authorized_scopes` | 智能体可处理的范围（仅供参考） |
| `risky_scopes` | 始终强制确认的范围（`external_send`、`delete`、`paid`、`publish`） |
| `always_confirm` | 永远钉在确认的类（最高优先级） |
| `auto_scopes` | 预授权的安全类 → 装上即 AUTO（永不阻塞） |
| `confidence` / `last_seen` | 各决策类学到的置信度 + 新鲜度（由 `learn.py` 管理） |
| `preferences` | 各决策类上次选择 id + 理由（由 `learn.py` 管理） |
| `gap_log` | 未知类首次解决的审计记录 |
| `remediation_style` | `correct.py` 使用的 persona 特质（phases、prefer_direct、plan_before_action、backup_before_change） |
| `decay_days` | 多少天未碰后置信度衰减（0 = 关闭） |

## 隐私与安全

- **无网络。** 全部本地文件，无遥测、无 API key。
- **决策过程不进 LLM。** 裁决是纯文件 + 数学，推理便宜且可复现。
- **危险动作无法自主。** 发送 / 删除 / 付费 / 发布 永远需要你，`auto_scopes` 也不能绕过。
- **你始终掌控。** 置信度是" earned trust"的代理指标而非概率；安全闸门无视它。

## 相关项目

本技能刻意做得很小，并借鉴了几个公开思路（已致谢，非抄袭）：

- **[selinayfilizp/decision](https://github.com/selinayfilizp/decision)** — `DECISION.md` 的"判断层" + Gap Protocol，启发了未知类的处理。
- **dot-skill / colleague-skill** — "修正层"思路（记录用户真实选择并复用），启发了 `preferences[class]`。
- **GitHub Issues Agent 的置信度门控** — 阈值→自主 / 理由审计的模式。
- **Jev decision layer** — 另一种 token-ROI / 多 key 路线，我们**刻意没有**采用，以保持零依赖。

本项目的独有之处：把**按类置信度学习 + auto_scopes 快速起步 + 无人值守 JSONL 复核闭环 + 按 persona 驱动改正**组合成一个零运行时依赖、可即插即用的技能。

## 许可证

MIT — 见 [LICENSE](LICENSE)。
