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
vale.ini            the generated config, or the user's edit of it
styles/ai-tells/    downloaded by `vale sync`
.synced-version     which package release styles/ came from
.config-hash        what the last generated vale.ini looked like
```

`check` and `check-text` both call `vale --config=<that vale.ini>`, so Vale
reads the plugin's configuration no matter which directory the command runs in
or what the surrounding project's own `.vale.ini` says. A missing or outdated
download triggers a sync first, and the version stamp is what makes that
detectable.

`check-text` writes stdin to a temporary `draft.md` before linting it. Vale
selects a parser by file extension, and Markdown is what loose prose already
is. The temporary path is replaced with `draft` in the output, because a path
under `/var/folders` tells the reader nothing.

## Key decisions

- **Cache directory, not the plugin directory.** Claude Code installs plugins
  into a versioned cache that a plugin update replaces. Downloaded styles and
  the user's config edits have to outlive that, so they live under
  `$XDG_CACHE_HOME`, with `$AI_TELLS_HOME` as an override that the tests use.

- **The style applies to `[*]`, every extension.** Vale reads source files by
  extension and pulls the comments and docstrings out of the ones whose
  language it knows, which is exactly the prose worth linting in a code file.
  Scoping the style to `[*.md]` instead would leave a Python or Go file with no
  rules attached, and Vale answers that with silence rather than an error, so
  the linter would look like it had found nothing. The cost is the other
  direction: a YAML or Terraform file, which Vale has no parser for, is read as
  prose end to end, and its keys and string values match rules meant for
  sentences. Noise a reader can see through beats a clean exit that means
  nothing. Vale's `[formats]` mapping does not rescue those formats, since only
  extensions Vale already classifies can be remapped, and the rest come back
  empty.

- **Only an untouched config is refreshed.** `.config-hash` holds a digest of
  the last config the plugin generated, so a file matching it is known to be
  nobody's work and can be rewritten when this script's template changes. A
  file that does not match belongs to the user. Turning rules off is the
  plugin's only real tuning mechanism, because every rule in the package is set
  to `error` level and `MinAlertLevel` filters nothing, so quieting one means
  naming it. Those names must survive an update. When such a config no longer
  matches the template, `check` and `status` say so and name `sync --force`,
  the one command that discards it.

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
generated config's contents, when a config is refreshed and when it is left
alone, when a sync is considered necessary, the `--output` flag forms,
temporary-path relabelling, and the command-line failure messages. These run
offline and on a machine with no Vale installed.

`TestAgainstVale` is the one group that shells out. Whether a `.py` file is read
as comments or as prose is Vale's decision rather than this script's, and
asserting on what the config says cannot show which way Vale went, so those
tests run the real binary over the styles in the cache. They build a cache of
their own with a freshly generated config and a symlink to those styles, since
the developer's own config may have rules switched off in it. They skip when
Vale or the styles are missing, and they download nothing.
