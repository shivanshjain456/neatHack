#!/usr/bin/env python3
"""Fast FFmpeg-backed Procedural Sound Engine + Voiceover Mixer + Synchronized Caption Generator.

- Uses FFmpeg's C filtergraph (`aevalsrc`, `adelay`, `amix`, `loudnorm`) to synthesize subtle
  harmonic transition chimes & warm ambient pad (-32 dBFS) and mix the 6 registered `voice-00`
  narration tracks at exact timeline timestamps in ~2 seconds.
- Outputs:
  1. public/audio/master_track_170s.wav (48kHz stereo 16-bit PCM, mastered to -15 LUFS)
  2. src/captions.json (frame-accurate subtitle entries for Remotion on-screen caption rail)
  3. out/verifix_neathack_2026_demo.srt & out/verifix_neathack_2026_demo.vtt
"""

import json
import subprocess
from pathlib import Path

VIDEO_DIR = Path("/home/user/verifix/video")
AUDIO_DIR = VIDEO_DIR / "public" / "audio"
MASTERED_DIR = AUDIO_DIR / "mastered"
OUT_DIR = VIDEO_DIR / "out"
SRC_DIR = VIDEO_DIR / "src"

OUT_DIR.mkdir(parents=True, exist_ok=True)
SRC_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_DURATION_SEC = 170.0

SCENES = [
    {
        "id": "scene_01",
        "title": "The Silent Caller Trap & Live Autonomous Recovery",
        "start_sec": 0.0,
        "end_sec": 28.0,
        "vo_start_sec": 0.35,
        "wav": MASTERED_DIR / "scene_01_hook.wav",
        "sentences": [
            "Most coding agents make a failing unit test pass while silently breaking downstream callers.",
            "VeriFix is an autonomous bug-remediation agent that maps your repository's call graph before editing a single line of code.",
            "Watch run 3061 on our live Mission Control dashboard: Attempt 1 passes the target test, but breaks a downstream settlement caller.",
            "VeriFix's guardrail blocks the commit, rolls back the worktree, and self-heals on Attempt 2.",
        ],
    },
    {
        "id": "scene_02",
        "title": "Deterministic State Machine, 4 Multi-File Repos & AWS Lambda Verifier",
        "start_sec": 28.0,
        "end_sec": 57.5,
        "vo_start_sec": 28.30,
        "wav": MASTERED_DIR / "scene_02_workflow.wav",
        "sentences": [
            "Every run executes a deterministic state machine across isolated Git worktrees and a transactional SQLite write-ahead ledger.",
            "Across 4 multi-file Python repositories—covering ledger rounding, rate limiters, webhook HMAC validation, and DAG schedulers—",
            "VeriFix localizes the defect, plans a testable hypothesis, verifies every caller contract,",
            "and signs each patch with our live AWS Lambda verifier in us-east-1.",
        ],
    },
    {
        "id": "scene_03",
        "title": "Partner #1: Entire (Graph v0.4.0 · Brain v0.1.0 · 13 Checkpoints · Agent Plugin)",
        "start_sec": 57.5,
        "end_sec": 85.0,
        "vo_start_sec": 57.85,
        "wav": MASTERED_DIR / "scene_03_entire.wav",
        "sentences": [
            "Entire powers both our runtime context and development provenance.",
            "At runtime, Entire Graph queries 1,635 AST records to isolate exact symbol slices and direct callers,",
            "while Entire Brain recalls durable architectural invariants across 465 symbols.",
            "For provenance, we built a native Entire External Agent plugin and recorded 13 Git Checkpoints with full token and line attribution.",
        ],
    },
    {
        "id": "scene_04",
        "title": "Partner #2: Neatlogs (275 Traces · 11 Detections · -65.05% Prompt Tokens)",
        "start_sec": 85.0,
        "end_sec": 116.5,
        "vo_start_sec": 85.35,
        "wav": MASTERED_DIR / "scene_04_neatlogs.wav",
        "sentences": [
            "Neatlogs traces every workflow, retriever, tool, guardrail, and model span—and connects back to the agent through the live Neatlogs MCP server.",
            "Across 275 production traces and 556+ tool calls with a 0.0% tool error rate, Neatlogs revealed severe context bloat in our naive baseline.",
            "Switching to graph-guarded retrieval cut prompt tokens by 65.05% and reduced latency by 42.56%,",
            "eliminating unguarded execution failures across 11 active Neatlogs detections.",
        ],
    },
    {
        "id": "scene_05",
        "title": "Partner #3: cfo.ai (plan.xlsx 4-Sheet Workbook · -79.83% Modeled COGS · 94.67% Proj. Margin)",
        "start_sec": 116.5,
        "end_sec": 143.0,
        "vo_start_sec": 116.85,
        "wav": MASTERED_DIR / "scene_05_cfo.wav",
        "sentences": [
            "Those measured Neatlogs token savings flow directly into our cfo.ai business model and 4-sheet formula workbook, plan.xlsx.",
            "Cutting modeled enterprise inference cost by 79.83%—down to $0.1794 per verified run—transforms our projected unit economics:",
            "delivering a projected 94.67% Q4 gross margin after Dodo Payments fees,",
            "and projected cash-flow positive infinite runway by Month 4.",
        ],
    },
    {
        "id": "scene_06",
        "title": "Real Upstream OSS Bug Fixed in neatlogs/neatlogs (Issue #199 & PR #203)",
        "start_sec": 143.0,
        "end_sec": 170.0,
        "vo_start_sec": 143.35,
        "wav": MASTERED_DIR / "scene_06_oss_and_close.wav",
        "sentences": [
            "To prove VeriFix beyond benchmarks, we pointed it at the official Neatlogs Python SDK itself.",
            "VeriFix uncovered a real thread-pool starvation bug in masking_exporter.py that dropped concurrent span batches,",
            "synthesized a deadline-bounded fix passing all 530 unit tests, and we opened Issue #199 and Pull Request #203 upstream.",
            "VeriFix: autonomous patches you can trust to ship.",
        ],
    },
]


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    )
    return float(out.strip())


def format_srt_ts(sec: float) -> str:
    ms_total = int(round(sec * 1000))
    hrs = ms_total // 3600000
    ms_total %= 3600000
    mins = ms_total // 60000
    ms_total %= 60000
    secs = ms_total // 1000
    ms = ms_total % 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def format_vtt_ts(sec: float) -> str:
    return format_srt_ts(sec).replace(",", ".")


def main() -> None:
    captions = []
    inputs = []
    filter_parts = []

    # Input 0: subtle stereo harmonic ambient pad (-32 dBFS) across 170s
    pad_expr = "0.012*sin(2*PI*110*t)+0.008*sin(2*PI*164.81*t)+0.006*sin(2*PI*220*t)"
    inputs.extend(["-f", "lavfi", "-t", str(TOTAL_DURATION_SEC), "-i", f"aevalsrc='{pad_expr}|{pad_expr}':s=48000"])
    filter_parts.append("[0:a]afade=t=in:st=0:d=1.5,afade=t=out:st=167.5:d=2.5[pad]")

    # Inputs 1..6: the 6 mastered voiceover tracks delayed to their exact scene start timestamps
    mix_labels = ["[pad]"]
    for idx, scene in enumerate(SCENES, start=1):
        wav_path = scene["wav"]
        vo_dur = probe_duration(wav_path)
        inputs.extend(["-i", str(wav_path)])
        delay_ms = int(round(scene["vo_start_sec"] * 1000))
        lbl = f"[vo{idx}]"
        filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume=1.0{lbl}")
        mix_labels.append(lbl)

        # Build proportional sentence captions
        sents = scene["sentences"]
        total_chars = sum(len(st) for st in sents)
        cur_t = scene["vo_start_sec"]
        for st in sents:
            share = (len(st) / total_chars) * vo_dur
            st_start = round(cur_t, 2)
            st_end = round(cur_t + share, 2)
            captions.append(
                {
                    "index": len(captions) + 1,
                    "scene_id": scene["id"],
                    "start_sec": st_start,
                    "end_sec": st_end,
                    "start_frame": int(round(st_start * 30)),
                    "end_frame": int(round(st_end * 30)),
                    "text": st,
                }
            )
            cur_t += share

    # Input 7: subtle transition chime (0.7s harmonic chord) repeated at scene boundaries
    chime_wav = AUDIO_DIR / "chime_unit.wav"
    chime_expr = "(0.035*sin(2*PI*523.25*t)+0.025*sin(2*PI*659.25*t)+0.018*sin(2*PI*783.99*t))*exp(-4.5*t)"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-t",
            "0.75",
            "-i",
            f"aevalsrc='{chime_expr}|{chime_expr}':s=48000",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(chime_wav),
        ],
        check=True,
        capture_output=True,
    )
    chime_times = [0.02, 8.0, 28.0, 57.5, 85.0, 116.5, 143.0, 161.0]
    base_idx = len(SCENES) + 1
    for c_i, ct in enumerate(chime_times):
        in_idx = base_idx + c_i
        inputs.extend(["-i", str(chime_wav)])
        d_ms = int(round(ct * 1000))
        lbl = f"[ch{c_i}]"
        filter_parts.append(f"[{in_idx}:a]adelay={d_ms}|{d_ms}{lbl}")
        mix_labels.append(lbl)

    total_mix_inputs = len(mix_labels)
    filter_parts.append(
        f"{''.join(mix_labels)}amix=inputs={total_mix_inputs}:duration=first:dropout_transition=0:normalize=0,"
        f"loudnorm=I=-15:TP=-1.5:LRA=9[outa]"
    )
    filter_complex = ";".join(filter_parts)

    final_wav = AUDIO_DIR / "master_track_170s.wav"
    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[outa]",
        "-t",
        str(TOTAL_DURATION_SEC),
        "-ar",
        "48000",
        "-ac",
        "2",
        str(final_wav),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    chime_wav.unlink(missing_ok=True)

    # Write captions.json, .srt, and .vtt
    (SRC_DIR / "captions.json").write_text(json.dumps(captions, indent=2), encoding="utf-8")

    srt_lines = []
    vtt_lines = ["WEBVTT", ""]
    for c in captions:
        srt_lines.append(str(c["index"]))
        srt_lines.append(f"{format_srt_ts(c['start_sec'])} --> {format_srt_ts(c['end_sec'])}")
        srt_lines.append(c["text"])
        srt_lines.append("")

        vtt_lines.append(f"{format_vtt_ts(c['start_sec'])} --> {format_vtt_ts(c['end_sec'])}")
        vtt_lines.append(c["text"])
        vtt_lines.append("")

    (OUT_DIR / "verifix_neathack_2026_demo.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    (OUT_DIR / "verifix_neathack_2026_demo.vtt").write_text("\n".join(vtt_lines), encoding="utf-8")
    print(f"Built {final_wav} ({probe_duration(final_wav):.2f}s) and {len(captions)} synchronized caption cues.")


if __name__ == "__main__":
    main()
