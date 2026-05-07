---
description: Scan the current repo for secrets and internal/personal info that shouldn't be public.
allowed-tools: ["Bash", "Read", "Skill"]
---

Run the `public-ready` skill to scan the current Git repository for content that shouldn't be in a public repo.

Invoke the skill, then return its combined markdown report (Secrets / Possibly internal info / Verdict) to the user. Do not modify any files.
