---
name: anonymize-eval-prompts
description: Turn real user prompts, transcripts or Slack questions into anonymized eval cases for a skill, for example for step 2 of `claude plugin eval`. Removes private information and rewrites each prompt with lossless-text-compression so it keeps its point but no longer matches the original wording.
disable-model-invocation: true
---

# anonymize-eval-prompts

The people who wrote the original prompts must not recognize their prompt in the eval, and the eval must not reveal anything private about them. Each rewrite keeps the request, and whether the skill under test should help with it.

The checker is `${CLAUDE_PLUGIN_ROOT}/skills/anonymize-eval-prompts/check-rewrites.py`.

## 1. Collect the prompts

Ask for anything the user has not given yet:

- The skill under test, by name or by its description.
- The real prompts. For each prompt, ask whether the skill should or should not have helped, unless the user already said.

From a transcript or Slack thread, keep only the message that asks for something, plus the context the request needs to make sense.

Never write the originals into a repository. The only file that holds them is `cases.json` in the scratchpad directory, from step 4.

## 2. Remove private information

For each prompt, list every detail that could identify a person, team, organization or system:

- Names of people, teams, organizations and customers.
- Repository, service, host and domain names, URLs and internal system names.
- Ticket numbers, account IDs, email addresses, phone numbers, IP addresses and local file paths.
- Secrets or anything that looks like one. If you find one, tell the user.
- Dates, numbers and quoted error messages that tie the prompt to a specific event.
- Personal style that identifies the author, such as signature phrases, greetings or recurring typos.

Replace each detail with a fictional one of the same kind, so a repository name stays a plausible repository name. Keep public terms the skill should react to, such as tool names, file names from a public convention and CLI commands. Keep the prompt's language. Record the original values per prompt as its `private` list.

## 3. Rewrite with lossless-text-compression

Load the `lossless-text-compression` skill and follow it, with these changes:

- Write its files (the document, the statements and each version) to the scratchpad directory, not the working directory.
- Run it on all anonymized prompts as one document, with one section per prompt. Tell the compression agents never to move content between prompts.
- Write the verification statements about what each prompt asks for and which terms the skill should react to. Every statement names its prompt, for example "Prompt 3 asks for ...".
- Keep each rewrite sounding like a user typed it, in first person, not like documentation.

## 4. Check the rewrites

Write `cases.json` in the scratchpad directory, with one object per prompt: `{"original": ..., "rewrite": ..., "private": [...]}`. Then run:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/anonymize-eval-prompts/check-rewrites.py cases.json
```

It fails a case when the rewrite still contains a `private` term, or shares more than four consecutive words with the original. Rephrase failing rewrites and rerun until every case passes. A shared run that is a command or file name the skill must react to may stay. Tell the user which runs you kept and why.

## 5. Hand over

Show each rewrite with its label ("should help" or "should not help"), and ask the user to confirm that none of them identifies its author. When the user approves, give the list in a form they can paste into the eval, and delete `cases.json` and the files lossless-text-compression wrote.
