# Demo video v2 (current)

This cut is **2:18** (138.4 s, under X's 140-second limit for accounts without Premium), 1920×1080, 30 fps, H.264 + AAC 48 kHz, −16 LUFS, true peak −1.3 dBTP. The binary left the repo root on 2026-10-12 (judge tooling enforces a repo-size cap); download it at https://gofile.io/d/eipSA3Zd — sha256, byte size and measured specs are recorded in `verifix_neathack_2026_demo.meta.json` at the repo root, and `tests/test_demo_video.py` cross-checks the file against that metadata whenever it is present locally. Captions are in `verifix_neathack_2026_demo.srt` / `.vtt`.

## What is on screen

Real browser sessions against the live AWS Lambda deployment, recorded with Playwright on 11 Oct 2026 (IST). Nothing is mocked:

| Scene | What it shows |
| :--- | :--- |
| Verify screen | The 7 judge checks, loaded live from `/api/judge-proof` |
| Live run | Benchmark 1 with the *controlled failure test* switched on. Attempt 1 is a deliberately injected bad patch, labelled as such on screen. The real run `run_graph_case_01_le_25244` was caught, rolled back and verified on attempt 2 (2,273 tokens, neatlogs trace `958163a4…`) |
| neatlogs | Evidence tab, then the overview's controlled-experiment metrics. Caption figures come from `benchmarks/ablation_experiment.json` ([method](../../docs/EVALUATION.md)); `scripts/verify_claims.py` checks the narration and caption against the data |
| Entire | Checkpoint-linked commits and the caller-graph panel |
| cfo.ai | The financial view, rendered from the recalculated `plan.xlsx` (projections) |
| Open source | neatlogs issue #199 and pull request #203 |

## Rebuild

```bash
python3 record.py        # records raw/*.webm from the live deployment and writes raw/scenes.json
python3 make_cards.py    # title cards and scene labels
python3 build.py         # aligns narration to the recorded event timestamps and encodes the cut
python3 captions.py      # SRT/VTT from narration.json and the real segment timings
python3 loudnorm.py verifix_neathack_2026_demo_v2.mp4 final.mp4   # two-pass EBU R128 to -16 LUFS
```

Narration audio is synthesised from `narration.json` (voice-00). An earlier v1 pipeline produced a 2:50 cut that showed the pre-reconciliation interface and figures; it has been retired and removed from the public repository.

sha256 (first 16): `86571f162e2f5531`

`tests/test_demo_video.py` reads the duration from the MP4 header and fails if the cut exceeds 139.5 s or the captions drift from `narration.json`.

## Revision (11 Oct 2026)

The 2:20 cut said graph context gave "ninety-seven percent fewer tokens". That figure came from a single comparison against a handicapped baseline, so it was retired. The 2:27 cut re-recorded the Verify, run, neatlogs/overview and financial scenes against the updated deployment, and replaced narration n2, n5, n7 and n9 and the closing card. The new lines cited the controlled experiment, described the Verify screen's mix of live and recorded checks, labelled the stress test's historical input, and said that numbers are linked to evidence rather than all live.

The 2:27 cut was 7 s over X's 140-second limit for accounts without Premium. The 2:18 cut keeps every scene and recording and shortens only narration n5 (neatlogs, 27.9 s → 20.5 s) and n7 (financial plan, 19.5 s → 18.3 s). The n5 sentence on the controlled experiment and the retirement of the 97% figure are unchanged in substance; the per-test breakdown it used to read aloud remains on the on-screen caption.
