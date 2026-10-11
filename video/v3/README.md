# VeriFix v3 videos — Remotion + HyperFrames pipelines

Two judge-facing videos, rendered from code, 1920×1080 @ 30 fps, H.264. The full video is rendered with
**Remotion 4.0.534** (`src/`); the shipped 30 s highlight is rendered with **HyperFrames 0.8.145**
(`hf-highlight/`, HTML+GSAP composition); an alternate Remotion cut of the highlight also exists.

| Composition | Engine | Length | Purpose |
|---|---|---|---|
| `VeriFixFull` | Remotion | 3:12 (5,760 frames) | Full story: hook → problem → thesis → 6-step pipeline → caller-trap proof → controlled experiment → patch assurance → neatlogs/Entire/cfo.ai partners → supply-chain rigor → verify-it-yourself close |
| Highlight | HyperFrames | 0:30 (900 frames) | Highlight: hook → caller trap → headline numbers → evidence close |
| `VeriFixHighlight` | Remotion | 0:30 (900 frames) | Alternate cut of the highlight |
| `VeriFixSubmission` | Remotion | 2:58 (5,340 frames) | F3-compliant submission cut (≤ 3:00): the full 12-scene story at 0.927× — [download](https://gofile.io/d/yNMt8IBw) |

HyperFrames needs Node ≥ 22 and ffmpeg/ffprobe on PATH:

```bash
cd hf-highlight && npx hyperframes render --low-memory-mode -o /tmp/out.mp4
```

## Render

```bash
npm install
npx remotion render VeriFixFull out/VeriFix_Full.mp4 --crf 18
npx remotion render VeriFixHighlight out/VeriFix_Highlight.mp4 --crf 18
# Submission cut (178.0 s, under the 3:00 F3 ceiling) — lean profile used for the shipped file:
npx remotion render VeriFixSubmission out/VeriFix_Submission.mp4 --crf 20 --x264-preset veryfast --jpeg-quality 70
```

Headless-Chromium system libs required (`libnspr4`, `libnss3`, …).

## Structure

- `src/theme.tsx` — design system (palette, type, `useIn/useOut` springs, `Chrome` brand bar, `Card`, `Count` count-ups).
- `src/FullVideo.tsx` — 12 scenes, each with entry/exit animation windows; durations declared per scene.
- `src/HighlightVideo.tsx` — 4 segments.
- `src/Root.tsx` — composition registration.

## Copy rules (keep in sync with repo evidence)

Every number on screen is a measured, judge-checkable figure from the repo
(`scripts/verify_claims.py` recomputes them from raw runs): 62% fewer tokens (CI 58–68%), 20/20 judged,
24/24 injections blocked, C9 21/25 with 0/18 false blocks, 170 deterministic tests, 18 integration runs,
1,400+ neatlogs traces, M11 first +EBITDA / $2.26M M24 ARR are **projections** (labeled as such on screen).
Never use retired figures (-65.x% tokens, 79.8% COGS, $298K ARR, 165 tests).

Rendered mp4s are NOT committed (workspace size limits); they are distributed via gofile links.

## Downloads (rendered 2026-10-11)

- Full (Remotion): <https://gofile.io/d/Io92bIuk> (4,832,413 bytes)
- Highlight (HyperFrames, shipped): <https://gofile.io/d/PyixHf0U> (1,511,925 bytes)
- Highlight (Remotion, alternate cut): <https://gofile.io/d/hAPT6bAb> (705,738 bytes)

QA performed: container parse (duration 192.0 s / 30.0 s, avc1 H.264 yuv420p 1920×1080@30),
Chromium playback (videoWidth/Height 1920×1080, readyState 4, no decode errors), decoded
mid-stream frames match the intended scene timeline, and every scene was visually QA'd as
PNG stills before rendering.
