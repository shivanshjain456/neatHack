"""Write SRT/VTT captions from the narration text and the real segment/clip timings."""
import json, re, subprocess
from pathlib import Path
D = Path(__file__).parent
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]))
text = json.loads((D/"narration.json").read_text())
meta = json.loads((D/"raw"/"scenes.json").read_text())
segs = [l.split("'")[1] for l in (D/"segments"/"list.txt").read_text().splitlines()]
starts, t = {}, 0.0
for s in segs: starts[s[:-4]] = t; t += dur(D/"segments"/s)
v = meta["s3_run"]["verified"] - meta["s3_run"]["ready"]
place = {"n1":("01_title",0.6),"n2":("02_verify",0.4),"n3":("03_run",0.3),"n4":("03_run",v+0.3),"n5":("04_neatlogs",0.3),
         "n6":("05_entire",0.4),"n7":("06_cfo",0.4),"n8":("07_oss",0.4),"n9":("08_close",0.6)}
cues = []
for k,(seg,delay) in place.items():
    a0, length = starts[seg]+delay, dur(D/"audio"/f"{k}.mp3")
    parts = [p for p in re.split(r"(?<=[.:?!])\s+", text[k]) if p]
    total = sum(len(p) for p in parts); cur = a0
    for p in parts:
        d = length*len(p)/total; cues.append((cur, cur+d-0.05, p)); cur += d
def ts(x, sep): h,m=int(x//3600),int(x%3600//60); s=x%60; return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int(round((s-int(s))*1000)):03d}"
srt = "".join(f"{i}\n{ts(a,',')} --> {ts(b,',')}\n{p}\n\n" for i,(a,b,p) in enumerate(cues,1))
vtt = "WEBVTT\n\n"+"".join(f"{ts(a,'.')} --> {ts(b,'.')}\n{p}\n\n" for a,b,p in cues)
(D/"verifix_neathack_2026_demo.srt").write_text(srt); (D/"verifix_neathack_2026_demo.vtt").write_text(vtt)
print(len(cues),"cues, last ends",round(cues[-1][1],2))
