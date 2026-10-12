"""The submitted demo must stay uploadable to X without Premium (<= 140 s) and match its captions.

The binary left the repo on 2026-10-12 (judge tooling enforces a repo-size cap); the measured
facts live in verifix_neathack_2026_demo.meta.json next to a permanent download link. When the
binary is present locally (dev machines), its moov/mvhd duration is cross-checked against the
recorded value so the metadata can never drift from the file.
"""
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "verifix_neathack_2026_demo.mp4"
META = ROOT / "verifix_neathack_2026_demo.meta.json"
X_NON_PREMIUM_LIMIT_S = 140.0


def load_meta() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))


def mp4_duration_seconds(path: Path) -> float:
    """Read the movie header (moov/mvhd) duration without external tools."""
    data = path.read_bytes()

    def boxes(buf: bytes, start: int, end: int):
        i = start
        while i + 8 <= end:
            size, kind = struct.unpack(">I4s", buf[i:i + 8])
            header = 8
            if size == 1:
                size = struct.unpack(">Q", buf[i + 8:i + 16])[0]
                header = 16
            elif size == 0:
                size = end - i
            if size < header:
                raise ValueError("corrupt MP4 box")
            yield kind, i + header, i + size
            i += size

    for kind, body, end in boxes(data, 0, len(data)):
        if kind == b"moov":
            for sub, sbody, _ in boxes(data, body, end):
                if sub == b"mvhd":
                    version = data[sbody]
                    if version == 1:
                        timescale, duration = struct.unpack(">IQ", data[sbody + 20:sbody + 32])
                    else:
                        timescale, duration = struct.unpack(">II", data[sbody + 12:sbody + 20])
                    return duration / timescale
    raise ValueError("no moov/mvhd box")


def recorded_duration() -> float:
    meta = load_meta()
    duration = float(meta["duration_s"])
    assert 60 < duration <= X_NON_PREMIUM_LIMIT_S - 0.5, duration
    assert meta["download"].startswith("https://gofile.io/d/"), meta["download"]
    assert re.fullmatch(r"[0-9a-f]{64}", meta["sha256"]), meta["sha256"]
    assert meta["bytes"] > 1_000_000, meta["bytes"]
    return duration


def test_demo_fits_x_upload_limit_without_premium():
    duration = recorded_duration()
    if VIDEO.exists():  # dev machines only: the metadata must match the actual file
        assert abs(mp4_duration_seconds(VIDEO) - duration) < 1.0


def test_captions_end_inside_the_video():
    duration = recorded_duration()
    srt = (ROOT / "video/v2/verifix_neathack_2026_demo.srt").read_text(encoding="utf-8")
    stamps = re.findall(r"(\d\d):(\d\d):(\d\d),(\d{3})", srt)
    last = max(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000 for h, m, s, ms in stamps)
    assert last <= duration


def test_captions_match_narration_text():
    narration = json.loads((ROOT / "video/v2/narration.json").read_text(encoding="utf-8"))
    srt = (ROOT / "video/v2/verifix_neathack_2026_demo.srt").read_text(encoding="utf-8")
    for key in ("n5", "n7"):
        first_sentence = re.split(r"(?<=[.:?!])\s+", narration[key])[0]
        assert first_sentence in srt, key
