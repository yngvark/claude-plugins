# ai-tells

Lints prose for AI writing tells using
[vale-ai-tells](https://github.com/tbhb/vale-ai-tells), a package of 111
[Vale](https://vale.sh) rules built from research into how AI-generated prose
differs from human prose.

Nothing is added to the project you are working in. The plugin keeps its own Vale
config and its own copy of the styles under `~/.cache/vale-ai-tells`, so any
text can be linted regardless of whether the repository uses Vale.

## Requirements

Vale, installed separately:

```bash
brew install vale
```

The first lint downloads the style package and needs network access. Everything
after that runs locally.

## Use

Ask for a check in any session ("does this README sound like AI?"), or run the
command:

```
/ai-tells docs/design.md
```

With no argument the command checks the prose files changed in the working tree.

Directly, from a shell:

```bash
scripts/ai_tells.py check README.md          # lint files
scripts/ai_tells.py check-text < draft.txt   # lint text on stdin
scripts/ai_tells.py status                   # what is installed, which version
scripts/ai_tells.py sync --force             # rewrite config, re-download styles
scripts/ai_tells.py config-path              # where the config lives
```

Findings print as `file:line:column:rule:message`. Exit code 1 means findings
were reported.

## Turning rules off

The package sets its rules to `error` level, so `MinAlertLevel` cannot thin
the output.
Quieting a rule means naming it. Add a line under the `[*.md]` section of the
config that `config-path` points at:

```ini
ai-tells.EmDashUsage = NO
```

That file is generated once and left alone afterwards. Only `sync --force`
overwrites it.

## What is not included

The upstream project also publishes `ai-tells-commits` (commit message rules) and
`ai-tells-experimental` (structural rules its author marks as opt-in and noisy).
Neither is installed here.

## Tests

```bash
make test
```

Design notes: [`docs/ai-tells.md`](../../docs/ai-tells.md).
