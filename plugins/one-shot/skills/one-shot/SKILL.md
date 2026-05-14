---
name: one-shot
description: Activate one-shot mode for the rest of this session — delegate every clarifying question to the one-shot-decider subagent so the user is not interrupted during design or implementation. Use this when the user runs /one-shot or asks to enable one-shot mode. The user supplies high-level intent once; all subsequent decisions are made by the decider, logged to a project file, and the user is only re-interrupted for plan-mode plan approval (ExitPlanMode).
---

# One-Shot Mode

The user has activated one-shot mode. For the rest of this session, follow these rules.

## Rule 0 — bootstrap the preferences file on first use

The user's preferences live at `~/.claude/one-shot/preferences.md` (global, user-editable, persists across sessions and plugin updates).

On the first delegation in this session, check whether that file exists. If it does NOT exist:

1. Create the directory `~/.claude/one-shot/` if missing.
2. Copy `${CLAUDE_PLUGIN_ROOT}/skills/one-shot/preferences.template.md` to `~/.claude/one-shot/preferences.md`.
3. Tell the user once, in plain text: "Created default preferences at `~/.claude/one-shot/preferences.md` — edit anytime to tune one-shot decisions."

Never write user preferences inside the plugin tree — plugin updates would clobber them.

## Rule 1 — delegate every clarifying question

Whenever you would otherwise ask the user a clarifying question, do NOT ask the user. Instead, spawn the decider subagent via the `Agent` tool with `subagent_type: one-shot:one-shot-decider` (the plugin-namespaced form — the unqualified `one-shot-decider` will fail with "Agent type not found") and use its answer.

This applies to:
- Clarifying questions during brainstorming, design, or planning.
- Mid-implementation choices ("should I use library X or Y?", "should this be a class or a function?").
- `AskUserQuestion` tool calls — replace them with a decider spawn.
- Any other question you would direct at the user.

This does NOT apply to:
- `ExitPlanMode` — plan-mode plan approval still goes to the user. This is the one approval gate.
- Tool permission prompts surfaced by Claude Code itself (those are not yours to control).

## Rule 2 — initialize the session log on first delegation

On the first delegation in this session, create the log file:

```
<project>/one-shot-log/<YYYY-MM-DD-HHMMSS>.md
```

Where `<project>` is the current working directory and the timestamp is the moment of the first delegation. Create the directory if it does not exist. Write a header in this exact format (note the two trailing spaces on the metadata lines — they render as soft line breaks; no `---` separator):

```markdown
# One-Shot session log

**Started:** <ISO 8601 timestamp>  
**Working directory:** <cwd>  
```

Tell the user once, in plain text: "One-shot mode active. Decisions will be logged to `<path>`."

## Rule 3 — subagent invocation template

When you spawn the decider, use this exact prompt structure:

```
You are answering on behalf of the user. The user is in one-shot mode.

## Preferences
<paste full contents of ~/.claude/one-shot/preferences.md>

## Project context
Working directory: <cwd>
What we're working on: <one-paragraph summary of the current task>

## Question
<verbatim question you would have asked the user>

## Options offered (if any)
<A/B/C list, or "open-ended">

Decide. Output as:
ANSWER: <one-line decision>
REASONING: <2-3 sentences>

Do not ask follow-up questions. If the question would normally require user-only input (e.g., plan approval), output: ANSWER: REDIRECT_TO_USER
```

Always read `~/.claude/one-shot/preferences.md` fresh on each delegation (the user may edit it between questions).

## Rule 4 — log every Q&A

After each delegation succeeds, append to the session log. Each entry MUST include the full question AND the answer with reasoning directly below it. Never log answers without their questions. Never batch reasoning at the end of the log — keep it inline with each entry.

Use this exact format (blank line between every labeled subsection; no `---` separator between entries; no inline timestamp in the heading):

```markdown
## Q<N>: <short question summary>

**Question:** <question text, ending at the question mark — do NOT inline the option list>

A) <option A>
B) <option B>
C) <option C>

**Options offered:** <A/B/C if any, else N/A>

**Answer:** <subagent's ANSWER line>

**Reasoning:**
<subagent's REASONING text>
```

Formatting rules:

- Heading is `## Q<N>: <summary>` — no `[HH:MM:SS]` timestamp.
- If the question text contains options inline (e.g. "...which design? A) ... B) ... C) ..."), strip them out: keep only the question itself in `**Question:**`, then list each option on its own line below, separated by a blank line above and below.
- If the question has no options, omit the option block entirely and write `**Options offered:** N/A`.
- `**Reasoning:**` is followed by a newline; the reasoning text goes on the next line, not inline after the label.
- Do NOT write a `---` separator between entries.

Where `<N>` is the question number within the session (Q1, Q2, ...). The main agent (you) writes the log — the subagent does not need Write access. Write each entry immediately after the delegation completes — do not defer logging to the end.

## Rule 5 — do not narrate Q&A back to the user

After delegating, just continue the work. Do not summarize each Q&A to the user mid-stream. The log is the report. At the end of the task, mention the log path so the user knows where to review decisions.

## Rule 6 — error handling

- **Decider returns malformed output (no `ANSWER:` line):** retry once with the prompt "Your previous response did not include the required `ANSWER:` line. Re-answer in the required format." If second attempt also fails, log it as `**Note:** decider failed, main agent decided.` and decide yourself.
- **Decider times out or errors:** same as above — log, decide, continue.
- **Log file write fails:** tell the user once, continue without logging this session.
- **Decider returns `ANSWER: REDIRECT_TO_USER`:** route the question to the user as normal.
- **`/one-shot` invoked again in the same session:** confirm "already active, log at `<path>`." Do not reset.

## Rule 7 — preferences are global, free-form

The preferences file at `~/.claude/one-shot/preferences.md` is the user's free-form notes. Pass the whole file to the decider every time. Do not parse, schema-check, or normalize it.
