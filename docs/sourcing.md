# Sourcing conventions from transcripts

Every rule in this repo should trace to something I actually said, repeatedly.
Invented best practices get ignored; codified corrections stick.

## Where the evidence lives

Claude Code writes one JSONL file per session under:

```
~/.claude/projects/<slugified-repo-path>/<session-uuid>.jsonl
```

Each line is one event. Real user turns are `.type == "user"` where
`.message.content` is either a string or an array containing `{"type":"text"}`
blocks. Everything else on that type is noise: tool results, `<system-reminder>`
blocks, `<command-name>` slash-command echoes, and compaction summaries.

## Extracting user turns

```bash
jq -r 'select(.type=="user")
       | .message.content
       | if type=="string" then . else (.[]? | select(.type=="text") | .text) end' \
   session.jsonl | grep -v '^<'
```

Work in chunks. A busy session file can exceed 25 MB and will blow out a context
window if read whole.

## What counts as signal

Ranked by how reliably it predicts a rule worth writing down:

1. **Anger and repetition.** "I swear I just said to fix that." A correction
   delivered twice is a missing convention; delivered angrily, a load-bearing one.
2. **Status interrogation.** "Is it deployed?" "Is it all fixed now?" Every time I
   have to ask, the agent's completion report was missing a field.
3. **Cross-session recurrence.** The same defect reappearing weeks later means the
   original fix was never verified against the running artifact.
4. **Standing directives.** Instructions phrased as universals ("never", "always",
   "throughout") rather than as this-task requests.

Discount one-off task detail, and discount sessions that are off-topic for the
repo they were recorded in — they carry no reusable preference.

## Where a finding belongs

| Signal | Destination |
|---|---|
| True regardless of repo or stack | `home/CLAUDE.md` |
| True for one repo's domain or deployment | that repo's own `CLAUDE.md` |
| A repeatable procedure with steps and checks | a skill in the matching plugin |
| A procedure I invoke by name, on demand | a command in the matching plugin |

A rule that already exists upstream — in `home/CLAUDE.md` or a Superpowers skill —
does not get restated here. If it exists and still gets violated, that is worth
recording as a sharper, more specific rule, not a louder duplicate.
