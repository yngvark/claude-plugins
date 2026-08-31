---
name: ai-tells
description: Lint prose for AI writing tells with the vale-ai-tells Vale package. It flags overused vocabulary ("leverage", "seamless", "robust"), adjective-noun pairs ("comprehensive approach"), em dashes, "not just X, it's Y" contrasts, formulaic conclusions, sycophancy, and anthropomorphized tools. Use when the user runs /ai-tells, when they ask to check text for AI tells or AI slop, when they wonder whether something sounds like AI, or after drafting a README, design doc, PR description, source comments, or other prose a human will read. Works on any file type, including comments and docstrings in source code, and on draft text that is not in a file yet. Does not need Vale set up in the project.
allowed-tools: Bash
---

# ai-tells: lint prose for AI writing tells

[vale-ai-tells](https://github.com/tbhb/vale-ai-tells) is a package of 111 rules
for [Vale](https://vale.sh), built from research into how AI-generated prose
differs from human prose. This skill runs those rules without adding any Vale
configuration to the project being worked in. The config and the downloaded
styles live in a cache directory of their own.

## Running it

Lint files:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/ai_tells.py check README.md docs/design.md app.py
```

Lint text that is not in a file yet, such as a PR description, a commit message
body, or a paragraph about to be written into a document:

```bash
cat <<'EOF' | ${CLAUDE_PLUGIN_ROOT}/scripts/ai_tells.py check-text
This robust solution seamlessly leverages a comprehensive approach.
EOF
```

Both print one finding per line, as
`file:line:column:rule:message`. Exit code 1 means findings, 0 means clean.

The first run downloads the styles, which takes a few seconds and needs network
access. After that everything is local. `status` reports whether Vale is
installed and which package version is on disk. `sync --force` rewrites the
config and downloads the styles again.

Vale itself is a prerequisite. If it is missing the script says so and prints
the `brew install vale` line. Relay that to the user rather than trying to work
around it.

## Reading the findings

Each finding names the rule and says what to do about it. Treat them as
candidates, not verdicts. The package targets technical documentation and every
rule is set to `error` level, so a long document will produce a long list, and
some of it will be wrong for the text at hand.

Judgement calls worth making before editing:

- **A quoted or literal string is not the author's prose.** A finding inside a
  code block, a quoted error message, a CLI flag, or a cited title is noise.
- **Some words are the right word.** `robust` in a statistics context and
  `leverage` in a finance context are not tells.
- **Rewrite, do not substitute.** Swapping "leverages" for "uses" leaves the
  sentence shaped the same. The rules point at a sentence that says little.
  The fix is usually to say the specific thing instead.

Never suppress a finding by editing the user's text into something vaguer, and
never add Vale suppression comments (`<!-- vale off -->`) to their files without
asking.

## Fixing

When the user asks for fixes rather than a report:

1. Run the linter and read the findings alongside the surrounding text.
2. Rewrite the sentences that really do read as AI prose.
3. Run it again to confirm, and tell the user which findings you left alone and
   why.

A config that has been switched off in places, or one written by an older
version of this plugin, is left alone rather than replaced, and `check` says so
on stderr when it finds one. Pass that message on; regenerating is the user's
call, since it discards the rule lines they added.

If a rule keeps matching on a project where it does not apply, the fix is a line
in the config, not repeated hand-editing:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/ai_tells.py config-path
```

Show the user that path and the rule name, and let them decide. Their edits
survive. Once the config differs from what the plugin generates, `sync --force`
is the only command that rewrites it.

## What gets linted

Any file, not only Markdown. Vale chooses a parser from the extension, so a
source file in a language it recognises has its comments and docstrings linted
while the code around them is left alone. That covers Python, Go, Ruby, Rust,
Java, JavaScript, TypeScript, C, C#, PHP, Lua, R, Swift, Scala, Haskell and
Perl, alongside the markup formats.

An extension Vale has no parser for is read as plain prose from the first line
to the last. For YAML, Terraform, shell or JSON that means every key, flag and
string value is checked as if it were a sentence, which produces a lot of
findings that are not about anyone's writing. Read those with the file type in
mind, and report only what falls inside a real comment.

## Scope

- Prose, wherever it lives: READMEs, design docs, PR and issue bodies, source
  comments and docstrings, chat replies. Not the code itself.
- The `ai-tells-commits` style (commit message rules) and
  `ai-tells-experimental` (structural rules the upstream author marks as noisy)
  are not installed.
- This complements the `talk-normally` skill rather than replacing it. Vale
  catches mechanical tells by pattern. Judgement about what the text should say
  is still yours.
