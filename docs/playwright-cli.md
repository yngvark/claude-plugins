# playwright-cli

## What it is

A one-skill plugin that teaches Claude to drive a browser with the `playwright-cli` binary:
`open`, `goto`, `click`, `fill`, `snapshot`, `screenshot`, request mocking, tracing, video, and
named browser sessions. `skills/playwright-cli/` is the upstream Playwright-authored skill,
vendored unchanged; the plugin adds only packaging.

## Why it is a plugin

The skill is the intended entry point for browser work: a global instruction says to reach for it
whenever a UI change needs verifying, and Claude then reads the skill to learn the commands. That
only holds if the skill resolves in *every* repo.

As a project skill under `<repo>/.claude/skills/playwright-cli/`, it resolves in exactly the repos
that carry a copy — so the same instruction produced `Error: Unknown skill: playwright-cli`
everywhere else, and four repos each carried an identical duplicate to keep working. Shipping it
from this marketplace makes one installed copy available everywhere, and duplicating it per project
becomes unnecessary.

`~/.claude/skills/` would also make it global, but plugins are how the rest of these skills are
distributed: versioned, installed by name, and updated by pulling the marketplace instead of by
copying directories.

## Requires

`playwright-cli` on `PATH` (`npm install -g playwright-cli`). The skill falls back to
`npx playwright-cli` if the global binary is missing.
