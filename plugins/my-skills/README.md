# my-skills

Skills I find useful that don't necessarily belong together. They share one plugin so I don't have to install a new plugin every time I add a skill.

## Install

```
/plugin marketplace add yngvark/claude-plugins
/plugin install my-skills@yngvark
```

## Skills

### notification-summary

Run it with `/notification-summary`; Claude does not start it on its own. Summarizes the most important GitHub issues and PRs in your notifications into an HTML page in a temp dir, and opens it. The page starts with a few highlights of what to do now. Threads are sorted into "Needs you", "Worth reading" and a collapsed list of the rest, each with a short summary of where it stands.

![Example summary page, with fictional repositories and people](example/screenshot.png)

Pass a `github.com/notifications?query=...` URL or its query, or set a default:

```sh
export NOTIFICATION_SUMMARY_QUERY="topic:my-team author:alice author:bob"
```

Supported terms are `topic:`, `author:`, `repo:`, `org:`, `reason:`, `is:unread`, `is:pr` and `is:issue`. Needs the `gh` CLI, logged in.

### apply-writing-rules

Rules for prose a human will read: docs, PR descriptions, commit messages, comments, tickets. Claude loads the skill before writing such text, or you run `/apply-writing-rules`.

### anonymize-eval-prompts

Run it with `/anonymize-eval-prompts`. It turns real prompts, transcripts or Slack questions into eval cases for a skill, for example for step 2 of `claude plugin eval`. It removes private information, then rewrites each prompt with the `lossless-text-compression` skill so the prompt keeps its point but not its original wording. A script checks that no rewrite contains a removed detail or shares more than four consecutive words with its original. You approve the result before using it.

Needs the `lossless-text-compression` skill installed.

## Development

```sh
make test
```
