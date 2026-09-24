# my-skills

Skills I find useful that don't necessarily belong together. They share one plugin so I don't have to install a new plugin every time I add a skill.

## Install

```
/plugin marketplace add yngvark/claude-plugins
/plugin install my-skills@yngvark
```

## Skills

### notification-summary

Summarizes the most important GitHub issues and PRs in your notifications into an HTML page in a temp dir. Threads are sorted into "Needs you", "Worth reading" and a collapsed list of the rest, each with a short summary of where it stands.

Pass a `github.com/notifications?query=...` URL or its query, or set a default:

```sh
export NOTIFICATION_SUMMARY_QUERY="topic:my-team author:alice author:bob"
```

Supported terms are `topic:`, `author:`, `repo:`, `org:`, `reason:`, `is:unread`, `is:pr` and `is:issue`. Needs the `gh` CLI, logged in.

## Development

```sh
make test
```
