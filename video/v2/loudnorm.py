"""Two-pass EBU R128 loudness normalisation (-16 LUFS, -1.5 dBTP); video stream copied untouched."""
import json, subprocess, sys
src, dst = sys.argv[1], sys.argv[2]
target = "I=-16:TP=-1.5:LRA=11"
p1 = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", f"loudnorm={target}:print_format=json",
                     "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
m = json.loads(p1[p1.rindex("{"):p1.rindex("}") + 1])
af = (f"loudnorm={target}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
      f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
subprocess.run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-i", src, "-af", af, "-ar", "48000",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst], check=True)
p3 = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", dst, "-af", f"loudnorm={target}:print_format=json",
                     "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
r = json.loads(p3[p3.rindex("{"):p3.rindex("}") + 1])
print(json.dumps({"input_i": m["input_i"], "output_i": r["input_i"], "output_tp": r["input_tp"]}))
