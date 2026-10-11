# Demo video v2 (current)

`verifix_neathack_2026_demo.mp4` at the repository root is this cut: **2:20**, 1920×1080, 30 fps, H.264 + AAC 48 kHz, −16 LUFS. Captions are in `verifix_neathack_2026_demo.srt` / `.vtt`.

## What is on screen

Real browser sessions against the live AWS Lambda deployment, recorded with Playwright on 11 Oct 2026 (IST). Nothing is mocked:

| Scene | What it shows |
| :--- | :--- |
| Verify screen | The 7 judge checks, loaded live from `/api/judge-proof` |
| Live run | Benchmark 1 with the *controlled failure test* switched on. Attempt 1 is a deliberately injected bad patch, labelled as such on screen. The real run `run_graph_case_01_le_93931` was caught, rolled back and verified on attempt 2 (2,270 tokens, neatlogs trace `a84d1896…`) |
| neatlogs | Evidence tab, then the before/after metrics. Caption figures come from experiment `exp_24aa3f2776` |
| Entire | Checkpoint-linked commits and the caller-graph panel |
| cfo.ai | The financial view, rendered from the recalculated `plan.xlsx` (projections) |
| Open source | neatlogs issue #199 and pull request #203 |

## Rebuild

```bash
python3 record.py        # records raw/*.webm from the live deployment and writes raw/scenes.json
python3 make_cards.py    # title cards and scene labels
python3 build.py         # aligns narration to the recorded event timestamps and encodes the cut
python3 captions.py      # SRT/VTT from narration.json and the real segment timings
```

Narration audio is synthesised from `narration.json` (voice-00). The v1 pipeline in `video/` is kept for history; its 2:50 cut showed the earlier interface and pre-reconciliation plan figures.

sha256 (first 16): `520c9135e5ef1692`
