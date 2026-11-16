---
name: verify-live
description: Prove a change is actually running on the target system before reporting it done. Use after any edit to something that is deployed, containerised, served, or long-running — and whenever about to say "fixed", "deployed", "working", or "done". Rebuilds rather than restarts, then reads real behaviour as evidence.
---

# verify-live

A change is not done because the diff looks right. It is done when the running system demonstrates it.

This exists because the same defect kept coming back across sessions: the fix was correct in the file and never reached the process serving traffic. Every "did that actually land?" and "is it deployed?" is this skill's absence.

## When this applies

Anything with a gap between source and running state: a container, a service under a process manager, a dev server with a build step, a compiled binary, a deployed site, a scheduled job. It does not apply to a pure library change covered by a test run.

## Procedure

### 1. Identify what serves the change

Before touching anything, answer concretely — not from assumption:

- What process or container actually serves this code?
- Is the code baked into an image or artefact at build time, or mounted and read live?
- Where does it run — locally, in Docker, on a remote host?

Read the compose file, service definition, or deploy script to answer this. Guessing here is what produces phantom fixes.

### 2. Rebuild, don't just restart

**If the code is baked in at build time, restarting runs the old code.** This is the single most common failure. Rebuild the image or artefact, then recreate the process from it.

Only skip the rebuild when you have confirmed the source is mounted live and the runtime reloads it. Say which case you determined and why.

### 3. Confirm the new artefact is the one running

Not that a build succeeded — that the running thing is the new one. Any of: image digest or build timestamp against the container's current image, a version or build string the app reports, a startup log line from after the restart, file content read from inside the running container.

### 4. Exercise the actual behaviour

Drive the specific thing that was broken, and read the real output:

- **Service**: make the request; read the response and the logs it produced.
- **Bot or worker**: trigger a real message or job; read what it emitted, not just that it didn't crash.
- **UI**: load the page and look at it — the rendered result, at the viewport that matters, not the component source.
- **Scheduled job**: run it once manually rather than waiting for the schedule.

Read logs from **after** the restart. Old log lines proving old behaviour are the second most common false positive.

### 5. Check for silent breakage

Confirm nothing else fell over: process still healthy after a minute (not crash-looping), no new errors in the log, dependent services still connected.

### 6. Report the evidence

State what you observed, not what you expect:

> Rebuilt `api` (image `sha256:9f3c…`, built 14:02), recreated. Startup log shows `v0.4.1`. `POST /reindex` returned 202 and the worker log shows all 1,412 items processed with no errors. Container healthy 3 minutes on.

If you could not verify, say exactly that and why. An unverified change reported as done is worse than one reported as unverified.

## Failure modes

| Symptom | Cause |
|---|---|
| Fix "works" but the bug returns next session | Restarted instead of rebuilt; old code was still serving |
| Logs look clean | Read from before the restart, or the wrong container |
| Health check passes, feature still broken | Verified the process is up, not that the behaviour changed |
| Only one instance fixed | Multiple replicas, or a stale image on a second host |
| Works locally, not deployed | Verified the local dev server, never the deployed target |

## Notes

- **Never report from the diff.** "The change is in place" is not verification.
- **A recurring defect means the previous fix failed.** Don't re-explain the old fix — find out why it didn't hold.
- **Verification is read-only.** Reading logs, status and config on a live system is fine; anything that mutates real state or triggers real third-party requests needs an explicit ask first.
