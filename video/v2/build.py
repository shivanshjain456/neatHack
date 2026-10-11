"""Assemble the demo from recorded scenes, title cards, labels and narration."""
import json
import subprocess
from pathlib import Path

D = Path(__file__).parent
RAW, CARDS, AUD, SEG = D / "raw", D / "cards", D / "audio", D / "segments"
SEG.mkdir(exist_ok=True)
meta = json.loads((RAW / "scenes.json").read_text())


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]))


def segment(name, length, video=None, start=0.0, image=None, labels=(), audio=()):
    args = ["ffmpeg", "-loglevel", "error", "-y"]
    if image:
        args += ["-loop", "1", "-framerate", "30", "-t", f"{length}", "-i", str(image)]
    else:
        args += ["-ss", f"{start}", "-i", str(video)]
    for png, _, _ in labels:
        args += ["-loop", "1", "-framerate", "30", "-t", f"{length}", "-i", str(png)]
    for mp3, _ in audio:
        args += ["-i", str(mp3)]
    f = [f"[0:v]scale=1920:1080:flags=lanczos,fps=30,setsar=1,tpad=stop_mode=clone:stop_duration=10,trim=duration={length},setpts=PTS-STARTPTS[v0]"]
    cur = "v0"
    for i, (_, a, b) in enumerate(labels, start=1):
        f.append(f"[{i}:v]format=rgba,fade=t=in:st={a}:d=0.3:alpha=1,fade=t=out:st={b - 0.3}:d=0.3:alpha=1[o{i}]")
        f.append(f"[{cur}][o{i}]overlay=0:0:shortest=1[v{i}]")
        cur = f"v{i}"
    f.append(f"[{cur}]fade=t=in:st=0:d=0.25,fade=t=out:st={length - 0.3}:d=0.3,format=yuv420p[vout]")
    base = 1 + len(labels)
    for j, (_, delay) in enumerate(audio):
        ms = int(delay * 1000)
        f.append(f"[{base + j}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{j}]")
    f.append("".join(f"[a{j}]" for j in range(len(audio))) + f"amix=inputs={len(audio)}:normalize=0,apad,atrim=duration={length}[aout]")
    out = SEG / f"{name}.mp4"
    args += ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]", "-t", f"{length}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]
    subprocess.run(args, check=True)
    return out


n = {k: dur(AUD / f"{k}.mp3") for k in ("n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9")}
s3, s5, s8 = meta["s3_run"], meta["s5_neatlogs"], meta["s8_oss"]
verified = s3["verified"] - s3["ready"]
assert n["n3"] + 0.3 < verified + 0.3, "n3 would overlap n4"
run_len = max(s3["end"] - s3["ready"] - 0.5, verified + 0.3 + n["n4"] + 1.0)
plan = [
    segment("01_title", n["n1"] + 1.3, image=CARDS / "title.png", audio=[(AUD / "n1.mp3", 0.6)]),
    segment("02_verify", n["n2"] + 0.9, video=RAW / "s2_verify.webm", start=meta["s2_verify"]["ready"],
            labels=[(CARDS / "l_verify.png", 0.4, n["n2"] + 0.6)], audio=[(AUD / "n2.mp3", 0.4)]),
    segment("03_run", run_len, video=RAW / "s3_run.webm", start=s3["ready"],
            labels=[(CARDS / "l_run.png", 0.3, s3["run_started"] - s3["ready"]),
                    (CARDS / "l_run2.png", verified + 0.1, verified + 6.5)],
            audio=[(AUD / "n3.mp3", 0.3), (AUD / "n4.mp3", verified + 0.3)]),
    segment("04_neatlogs", n["n5"] + 1.0, video=RAW / "s5_neatlogs.webm", start=s5["ready"],
            labels=[(CARDS / "l_neat.png", 0.5, s5["overview"] - s5["ready"] - 0.3),
                    (CARDS / "l_tokens.png", s5["overview"] - s5["ready"] + 1.0, n["n5"] + 0.7)],
            audio=[(AUD / "n5.mp3", 0.3)]),
    segment("05_entire", n["n6"] + 0.9, video=RAW / "s6_entire.webm", start=meta["s6_entire"]["ready"],
            labels=[(CARDS / "l_entire.png", 0.4, n["n6"] + 0.6)], audio=[(AUD / "n6.mp3", 0.4)]),
    segment("06_cfo", n["n7"] + 0.9, video=RAW / "s7_cfo.webm", start=meta["s7_cfo"]["ready"],
            labels=[(CARDS / "l_cfo.png", 0.4, n["n7"] + 0.6)], audio=[(AUD / "n7.mp3", 0.4)]),
    segment("07_oss", n["n8"] + 1.1, video=RAW / "s8_oss.webm", start=s8["ready"],
            labels=[(CARDS / "l_oss.png", 0.4, n["n8"] + 0.8)], audio=[(AUD / "n8.mp3", 0.4)]),
    segment("08_close", n["n9"] + 1.6, image=CARDS / "close.png", audio=[(AUD / "n9.mp3", 0.6)]),
]
(SEG / "list.txt").write_text("".join(f"file '{p.name}'\n" for p in plan))
final = D / "verifix_neathack_2026_demo_v2.mp4"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(SEG / "list.txt"),
                "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
print(final, round(dur(final), 2), "s", final.stat().st_size, "bytes")
