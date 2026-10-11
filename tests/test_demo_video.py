"""The submitted demo must stay uploadable to X without Premium (<= 140 s) and match its captions."""
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "verifix_neathack_2026_demo.mp4"
X_NON_PREMIUM_LIMIT_S = 140.0


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


def test_demo_fits_x_upload_limit_without_premium():
    duration = mp4_duration_seconds(VIDEO)
    assert 60 < duration <= X_NON_PREMIUM_LIMIT_S - 0.5, duration


def test_captions_end_inside_the_video():
    duration = mp4_duration_seconds(VIDEO)
    srt = (ROOT / "video/v2/verifix_neathack_2026_demo.srt").read_text(encoding="utf-8")
    stamps = re.findall(r"(\d\d):(\d\d):(\d\d),(\d{3})", srt)
    last = max(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000 for h, m, s, ms in stamps)
    assert last <= duration


def test_captions_match_narration_text():
    import json
    narration = json.loads((ROOT / "video/v2/narration.json").read_text(encoding="utf-8"))
    srt = (ROOT / "video/v2/verifix_neathack_2026_demo.srt").read_text(encoding="utf-8")
    for key in ("n5", "n7"):
        first_sentence = re.split(r"(?<=[.:?!])\s+", narration[key])[0]
        assert first_sentence in srt, key
