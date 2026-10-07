---
name: apply-writing-rules
description: Rules for any text a human will read. Load before writing or editing READMEs, design docs, PR descriptions, issues, commit messages, code comments, tickets, dashboard descriptions or Slack messages, and when asked to shorten or review such text. Not for code or structured data.
---

# Writing rules

These rules apply to every piece of text you produce for a human to read: READMEs, technical
documents, design docs, pull request descriptions, commit messages, code comments, Jira tickets,
dashboard and column descriptions, Slack messages, and your own replies in chat.

There is one failure mode, and it appears in all of them: you write down your process instead of
serving the reader's purpose. The result is long, complete, well-organised, and useless. The failure
modes below are the shapes it takes; the sentence rules near the end are for the text that survives
them. A few rules are absolute and say so; deviate from the rest only for a reason you could defend
out loud.

## Before you write

Answer three questions. If you cannot answer them, you are not ready to write.

1. Who reads this, and what are they trying to do?
2. What do they already know?
3. What will they do differently after reading?

The reader was not there. They did not see the ticket, the diff, the conversation, the three
approaches you rejected, or the bug you hit halfway through. They arrived just now with a specific
question and they leave the moment it is answered.

## The three rules

**1. Every sentence must earn its place.** Apply the deletion test: remove the sentence. If the
reader would still do the right thing, it stays deleted. Length is not evidence of effort. It is a
cost you charge the reader.

**2. Describe the present, not the change.** Write the system as it is, for someone who has never
seen an earlier version. Some artifacts are exempt because the change *is* their subject: commit
messages, PR descriptions, release notes, changelogs and incident reviews. Call those the change
artifacts — everywhere else the change is invisible.

**3. Answer the reader's question, not yours.** What was hard, what you rejected, and why it exists
is your story. Include it only where the reader must act on it.

## Failure modes

### Structure without content

You produce headings, bullets and length because they signal thoroughness.

A two-line fix does not get *Summary / Motivation / Changes / Testing / Risks / Follow-ups*.

Instead of:

> ## Summary
> Fixes the timeout.
>
> ## Changes
> - Increased timeout
>
> ## Testing
> Ran the tests.

Write:

> Raised the HTTP client timeout to 30s. The partner API regularly takes over 20s under load.

Scale the shape of the text to the amount of content. A heading exists so a reader can skip to the
part they need, never to signal that the document is thorough — text under roughly 300 words
rarely earns one. One idea is one paragraph. Never write a section because a template implies it
should exist: no "Testing: N/A", no "Future work: none identified", no "Notes: —". If there is
nothing to say, delete the heading rather than fill it, and do not pad three items to equal length
because the first one was substantial.

### Restating the artifact

You tell the reader what they can already see.

Instead of:

> Adds `parseTimestamp` to `DateUtils.scala`. Updates `Importer.scala` to call it. Adds a test in
> `DateUtilsSpec.scala`.

Write:

> Timestamps from the partner feed have no timezone, so we assume UTC. Worth checking that holds
> for the Danish feed.

The diff already carries every word of the first version, so the reviewer learns nothing from it.
The same applies to a comment that restates its line of code, and a README that lists the
repository's directories.

### Historical residue

You write about the change instead of the state, outside the change artifacts.

Instead of:

> To lint, run `make lint` — no need to install the linter.

Write:

> To lint, run `make lint`.

The reader never knew a linter had to be installed. The sentence only makes sense to someone who
watched the project change, and it plants a question it then answers. Never write "no longer",
"previously", "used to", "as of this change", "unlike before", "we now do X instead of Y", or
"(formerly Z)" outside a change artifact.

### Rationale dumping

You explain why a thing exists to a reader who only wants to use it.

Instead of:

> Kept as its own model so the billing rules stay in dbt: the amount is net of refunds rather than
> gross charges. A consumer reading `fct_billing_daily` directly would have to know that, and an
> upstream column change would surface as a silently wrong number in the app instead of a failing
> build here.

Write:

> Amount is net of refunds, not gross.

The model name `fct_product_billing_daily` already says what the table holds and at what grain, so
none of that needs restating. Notice what does survive: net rather than gross, because a reader who
assumes gross gets a silently wrong number and no failing build. The design argument wrapped around
that one fact belongs in the PR that introduced the model, or nowhere. Rationale earns its place
only when the reader would otherwise do the wrong thing — change the value, delete the file, use the
wrong table.

### Insider vocabulary

You name things the way the work left them in your head, not the way the reader thinks about them.

Instead of:

> Carries `maxAmount`/`maxLoanToValue` through `InterestRateJson`.

Write:

> Adds optional `maxAmount` and `maxLoanToValue` bounds to the HTTP API.

The test: would the reader have phrased it this way *before* the work was done, or only after? If
only after, you have leaked implementation. Use the domain names the reader reasons about, never the
implementing class (`*Json`, `*Dto`, `*Mapper`). State a dependency's behaviour — "rejects the whole
header on one bad value" — never the call that produces it. Gloss or drop jargon from a stack the
reader does not work in: "Tapir" means nothing in a front-end repo, and "the backend" costs three
words.

### Explaining the reader's own system

You describe back to the reader the thing they maintain: a PR that opens by explaining what the
service does, a ticket that recaps the architecture, a reply that walks through their own pipeline.
You inferred the shape of it in an hour; they have lived in it for a year. Context earns its place
only where the reader plausibly lacks it — a component they do not own, a partner's behaviour, a
constraint you discovered rather than looked up.

### Hedging

You soften every claim so that none of them can be wrong.

Instead of:

> This should probably work in most cases, though it may be worth considering whether the timeout is
> perhaps a little too short.

Write:

> This works unless the partner API takes longer than 30s. I have not tested that case.

Blanket hedging destroys the reader's ability to tell a considered judgement from a guess, because
both end up sounding the same. Real uncertainty is worth stating — but state it as a fact about what
you know: which case is untested, which claim you inferred rather than verified, which number you
did not measure. A qualifier that does not name what is uncertain is only softening, and belongs
with the other filler below.

### Inflation

You use words that add length without adding information. Cut on sight: *it's worth noting that*,
*please note*, *in order to*, *this document aims to*, *as mentioned above*, *successfully*. Cut
bare qualifiers: *rather*, *quite*, *fairly*, *somewhat*, *arguably*, *it seems*, *it may be worth
considering*. Cut marketing adjectives: *robust*, *seamless*, *comprehensive*, *powerful*,
*elegant*. Cut the closing paragraph that summarises what the reader just read. Cut decoration:
no emoji unless the user used them first.

### Signposting

You write text about the text: "This section describes...", "The following table shows...", "Below
you will find...". The reader can see what is below. A signpost is always deletable, because the
thing it points at is always the next thing on the page. The only pointer worth writing is one that
travels — a link to something the reader cannot see from here.

### Explaining absences

You document what the thing does not do. "This does not handle retries." The list of things a system
does not do is infinite, so naming one is worth the words only when the reader arrives expecting it
and would act on the expectation — because the sibling component does handle retries, or because the
interface name implies it.

## Prose, not fragments

Succinct does not mean compressed. Cut whole ideas, not words. Write full sentences in paragraphs;
they carry reasoning that fragments cannot, and they are faster to read than a bulleted list of
noun phrases. Use a bulleted list only for genuinely parallel, enumerable items — never as a way to
avoid writing sentences. Never abbreviate to hit a length target — write `loanToValue`, not `LTV`.
Cut sections, not letters.

## Sentences

These are mechanical. Check them mechanically.

**One concept, one word.** Pick a term and never vary it. If it is a *job*, it is not later a
*task*, a *run*, or a *unit of work*. Synonyms feel like style to the writer and read as a
distinction to the reader, who then goes looking for a difference that is not there.

**Three nouns in a row, maximum.** "Partner feed timestamp validation failure" makes the reader
guess which noun modifies which. Break it apart with prepositions: "failures validating timestamps
in the partner feed."

**One instruction per sentence.** "Run the migration, then update the config and restart the
service" hides three steps in one line, and a reader executing them loses their place. Three
sentences, or three list items.

**Warnings before the step, never after.** A caution printed under the command is read after the
command has run. Put it in front of the thing it protects.

**Name the actor, in a verb.** "The config is loaded at startup" — by what? "Performs a validation
of the payload" — by what, and why not "validates the payload"? Passive voice and concept nouns
standing where verbs belong both cost words and drop the actor, often hiding that you do not know
which component is responsible.

## Titles and first sentences

A commit subject, PR title or ticket summary is read far more often than the text beneath it, and
usually on its own in a list, stripped of everything around it. It names the outcome, not the
activity: `Raise partner API timeout to 30s`, not `Fix timeout` and not `Changes to HttpClient`.
Whatever the title already carries, the body does not repeat.

The same weight falls on the first sentence of the body. It is the one sentence that gets read when
nothing else does, and signposting there costs more than signposting anywhere else: "I have made the
following changes" spends the most valuable position in the text on nothing. Open with the finding,
the answer, or the first instruction.

## How long

Anchors, not limits.

- **Code comment** — one line. If you need a paragraph, either the code needs fixing or the
  explanation belongs somewhere else.
- **PR description** — one to three sentences for most changes. A large one gets a short paragraph
  plus a pointer to what deserves attention.
- **README** — what this is, how to run it, how to work on it. Nothing more until someone asks.
- **Ticket** — enough that someone else could pick it up.
- **Chat reply** — as short as the question allows. An account of the steps you took is your
  process, not their answer; say what you did only where the reader must act on it.

Some documents genuinely need length: design documents, incident reviews, architecture decision
records. Length is fine there. The deletion test still applies to every sentence in them. Do not
answer these rules with timid, under-written text — an answer that omits something the reader needs
fails just as badly as one that buries it.

## What good looks like

```
const REFRESH_HOUR_UTC = 8  // The upstream dbt project runs at 07:00 UTC
```

The reader now knows not to lower the number. Everything else — that the gap absorbs an overrun,
that lowering it risks reading yesterday's data — follows from the one fact they were missing.

At a larger scale, a ticket someone else can pick up:

> `AdImporter` drops rows where `partnerId` is null, about 2% of the Danish feed. Either reject them
> at ingest or fill a placeholder; the data team owns that call, so ask them before implementing.

Present state, the decision to be made, and who decides it. Nothing about how it was found.

## Before you return the text

- Does every sentence survive the deletion test?
- Would this make sense to someone who never saw the diff, the ticket, or this conversation?
- Does anything restate what the code, the diff, or the title already says?
- Would the reader have used these words before the work was done, or only after?
- Is there a heading with less than a paragraph under it?
- Is there a bulleted list that is really three sentences of prose?
- Is there a closing paragraph that repeats what came before it?
- Could this be half as long without losing anything the reader needs?
