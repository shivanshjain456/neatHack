# Build-in-Public Record & Unposted Submission Drafts

**Status (2026-10-11):** Items in *Published* are live on X and count toward the
Building-in-Public criterion. Items in *Unposted drafts* are prepared material only —
they become part of the public record **only after Shivansh posts them himself**.
Nothing here may be posted by anyone else, and no draft may be backdated.

## Published (live on X, #neatHack window Oct 10–12)

| When | Link | Content |
| :--- | :--- | :--- |
| Oct 10, 2026 | [Post 1](https://x.com/sj909x/status/2108813809792299255) | VeriFix build update #1 |
| Oct 10, 2026 | [Post 2](https://x.com/sj909x/status/2108814094514204930) | VeriFix build update #2 |
| Oct 10, 2026 | [Reply in @neatlogs thread](https://x.com/neatlogs/status/2108855688026042598) | "what are you building?" — VeriFix one-liner |
| Ongoing | [neatlogs/neatlogs#199](https://github.com/neatlogs/neatlogs/issues/199) · [PR #203](https://github.com/neatlogs/neatlogs/pull/203) | Public upstream bug report + fix (real OSS contribution) |

## Unposted drafts — final submission quote post (Oct 12, 7:00–11:55 PM IST)

Official mechanics: **quote-post the official @neatlogs submission tweet
([status 2108855688026042598](https://x.com/neatlogs/status/2108855688026042598))**
with team, name, project, repo and demo. Attach the F3-compliant submission cut
(2:58) — download: <https://gofile.io/d/yNMt8IBw>.

**Draft S1 (canonical figures, ≤ 280 chars):**

```text
VeriFix — a coding agent not allowed to say "fixed" until it proves it.
Team HyperX · Shivansh Jain
62% fewer tokens, caller-regression rollback guardrail, real neatlogs race fixed upstream (PR #203).
Repo: github.com/shivanshjain456/neatHack
Demo 2:58 → gofile.io/d/yNMt8IBw
#neatHack
```

**Draft S2 (evidence-first variant, ≤ 280 chars):**

```text
Submitting VeriFix for #neatHack — Team HyperX (Shivansh Jain).
Every number links to evidence: 62% fewer tokens (CI 58–68%), 5/5 planted regressions rolled back, neatlogs SDK race → PR #203.
Repo github.com/shivanshjain456/neatHack · demo gofile.io/d/yNMt8IBw
```

Both drafts stay within 280 characters under X's t.co URL shortening (each URL
counts as 23 chars). Verify the count in the composer before posting.

## House rules

- Post only through @sj909x; never through another account.
- Never backdate, never fabricate engagement, never present a draft as published.
- If a figure changes before posting, update the draft here first and re-verify
  it against `scripts/verify_claims.py` output.
