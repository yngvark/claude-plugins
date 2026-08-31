# ai-tells plugin design

## Why

[vale-ai-tells](https://github.com/tbhb/vale-ai-tells) is a package of Vale
rules that flag the vocabulary and sentence shapes typical of AI-generated
prose. It is a style package rather than a program. The upstream instructions
tell you to add a `.vale.ini` to your project, point `Packages =` at a release
zip, and run `vale sync`.

That per-project setup is the wrong fit for how the user works. Text worth
linting is often not in a repository at all, such as a pull request body, an
issue description, or a paragraph being drafted before it is written to a file.
The repositories that do get prose written into them mostly have no Vale setup,
and they should not grow one just so an agent can lint a README.

So the plugin stores the Vale configuration instead of the project.

## How it works

`scripts/ai_tells.py` keeps a cache directory, `~/.cache/vale-ai-tells` by
default:

```
vale.ini            generated once, then left alone
styles/ai-tells/    downloaded by `vale sync`
.synced-version     which package release styles/ came from
```

`check` and `check-text` both call `vale --config=<that vale.ini>`, so Vale
reads the plugin's configuration no matter which directory the command runs in
or what the surrounding project's own `.vale.ini` says. A missing or outdated
download triggers a sync first, and the version stamp is what makes that
detectable.

`check-text` writes stdin to a temporary `draft.md` before linting it. Vale
selects rules by file extension and the generated config scopes the style to
`[*.md]`, so text has to reach Vale as a Markdown file. The temporary path is
replaced with `draft` in the output, because a path under `/var/folders` tells
the reader nothing.

## Key decisions

- **Cache directory, not the plugin directory.** Claude Code installs plugins
  into a versioned cache that a plugin update replaces. Downloaded styles and
  the user's config edits have to outlive that, so they live under
  `$XDG_CACHE_HOME`, with `$AI_TELLS_HOME` as an override that the tests use.

- **The config is generated once and never rewritten.** Only `sync --force`
  overwrites it. Turning rules off is the plugin's only real tuning mechanism,
  and that tuning belongs to the user. Every rule in the package is set to
  `error` level, which means `MinAlertLevel` filters nothing. Quieting a rule
  requires naming it, and a name the plugin overwrote on every sync would be
  useless.

- **StylesPath is written as an absolute path.** Vale resolves a relative
  `StylesPath` against the working directory in some invocations, and these
  commands run from wherever the user happens to be.

- **Version pinned in the script.** `PACKAGE_VERSION` names a release tag rather
  than tracking the latest. The package changes often, and a rule set that
  shifts under the user without warning would make one document's findings
  incomparable to the next. Bumping the constant makes the next run download
  again, because the stamp file no longer matches.

- **Prose style only.** The upstream project also publishes `ai-tells-commits`
  and `ai-tells-experimental`. The user does not lint commit messages, and the
  experimental structural rules are marked opt-in and noisy upstream. Adding
  either later means one more entry in `Packages` and `BasedOnStyles`.

- **Vale is a prerequisite, not something the plugin installs.** The script
  checks for the binary and prints the `brew install vale` line. Installing
  software on the user's machine without asking is worse than a clear error.

- **A skill rather than a hook.** A `PostToolUse` hook could lint every Markdown
  write automatically, but 111 error-level rules matching on every edit would
  drown the session. The skill triggers on request or after drafting prose,
  which keeps the user in control of when the noise arrives.

## Relationship to `talk-normally`

The user's global instructions already route human-facing text through the
`talk-normally` skill. That skill applies judgement about what a text should
say. This plugin runs a fixed set of pattern matches. They overlap, and the
overlap is deliberate, because findings from a mechanical linter are cheap to
check and occasionally catch something judgement missed. The skill file says so,
so that findings are read as candidates rather than verdicts.

## Tests

`test_ai_tells.py` covers what the script owns: cache location resolution, the
generated config's contents, when a sync is considered necessary, the `--output`
flag forms, temporary-path relabelling, and the command-line failure messages.
Nothing in the suite downloads styles or invokes Vale, so it runs offline and on
a machine with no Vale installed.
