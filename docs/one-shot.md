# Design: `one-shot` plugin

## Why this exists

During long design or implementation sessions, Claude Code regularly asks the user clarifying questions: "should I use library X or Y?", "class or function?", "test framework A or B?". Each question interrupts focus. For tasks where the user has already given clear high-level intent, most of these questions are tractable — they just need a decision against the user's known preferences.

`one-shot` mode delegates those decisions to a stand-in subagent (`one-shot-decider`) so the user is interrupted only for things that genuinely require human judgment.

## Architecture

Three components, all auto-discovered by Claude Code:

1. **Skill: `one-shot`** (`skills/one-shot/SKILL.md`)
   The activation entry point. When the user asks to activate one-shot mode, the skill loads a set of rules that the main agent follows for the rest of the session: delegate clarifying questions to the decider, log every Q&A, never narrate Q&As back to the user mid-stream.

2. **Subagent: `one-shot-decider`** (`agents/one-shot-decider.md`)
   Read-only subagent (tools: Read, Grep, Glob, WebSearch, WebFetch, Bash). Takes a question, the user's preferences, and project context. Outputs exactly two lines: `ANSWER:` and `REASONING:`. Has hard rules against follow-up questions and against modifying files. Returns `ANSWER: REDIRECT_TO_USER` for things only the human can decide (plan approval, sensitive credentials, taste with no preference signal).

3. **Preferences template** (`skills/one-shot/preferences.template.md`)
   Free-form markdown the user edits to tune decisions. Sections cover dependencies, code style, tradeoffs, testing.

## The one approval gate

`ExitPlanMode` (plan-mode plan approval) still goes to the user. That is intentional: the *plan* is the artifact the user needs to verify before code is written. Everything else can be delegated.

## The preferences-bootstrap pattern

Plugin updates must not clobber user preferences. Solution: ship a *template* inside the plugin, but write the *runtime* preferences file outside the plugin tree.

- Shipped: `${CLAUDE_PLUGIN_ROOT}/skills/one-shot/preferences.template.md`
- Runtime (user-editable): `~/.claude/one-shot/preferences.md`

On first delegation in any session, the skill checks for the runtime file and copies the template if it's missing. The user is told once where the file lives. Plugin updates touch the template, not the user's edits.

This is also why preferences are global rather than per-project: the user's tradeoff preferences ("prefer simpler over more flexible", "prefer fewer dependencies") are the user's, not the project's.

## Logging

Every delegation is logged to `<cwd>/one-shot-log/<YYYY-MM-DD-HHMMSS>.md` with question, options, answer, and reasoning. The log is the report — the main agent does not narrate decisions back to the user mid-stream. At the end of the task, the agent points the user at the log path.

This gives the user an audit trail without polluting the conversation. If a decision was wrong, they can see exactly what the decider was told and why it picked what it picked.

## Error handling

- Decider returns malformed output → retry once, then log "decider failed, main agent decided" and decide.
- Decider times out / errors → same.
- Decider returns `REDIRECT_TO_USER` → route the question to the user as normal.
- Log file write fails → tell the user once, continue without logging.
- `/one-shot` invoked again in the same session → confirm "already active", do not reset.

## Distribution

This plugin is distributed via the `yngvark` marketplace (this repo). To install:

```
/plugin marketplace add yngvark/claude-plugins
/plugin install one-shot@yngvark
```
