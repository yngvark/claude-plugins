# playwright-cli

Drives a browser through the `playwright-cli` binary — navigate, fill forms, click, snapshot,
screenshot, mock requests, record traces and video.

The skill activates whenever Claude needs to look at or interact with a web page, which is what
makes a global rule like "always use the playwright-cli skill to verify UI changes" work in every
repo instead of only the ones carrying a local copy of the skill.

```
/plugin install playwright-cli@yngvark
```

## Requires

`playwright-cli` on `PATH`:

```
npm install -g playwright-cli
```

The skill falls back to `npx playwright-cli` when the global binary is missing.

## Provenance

`skills/playwright-cli/` is the upstream Playwright-authored skill, vendored unchanged so it can be
distributed as part of this marketplace.
