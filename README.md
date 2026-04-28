# yngvark/claude-plugins

A Claude Code plugin marketplace.

## Install

In Claude Code:

```
/plugin marketplace add yngvark/claude-plugins
/plugin install one-shot@yngvark
```

## Plugins

### one-shot

Activate one-shot mode: a decider subagent answers clarifying questions on your behalf so you are not interrupted during design or implementation.

The user supplies high-level intent once; all subsequent decisions are made by a `one-shot-decider` subagent, logged to a per-session file under `<project>/one-shot-log/`, and the user is only re-interrupted for plan-mode plan approval.

After installing, activate by saying "activate one-shot mode" (or similar) in any session. On first use, default preferences are bootstrapped to `~/.claude/one-shot/preferences.md` — edit that file to tune how decisions are made on your behalf.

Design notes: [`docs/one-shot.md`](docs/one-shot.md).

## License

MIT — see [`LICENSE`](LICENSE).
