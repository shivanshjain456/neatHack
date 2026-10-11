"""Render title cards (opaque) and scene labels (transparent PNG) at 1920x1080."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "cards"
OUT.mkdir(exist_ok=True)
FONT = "font-family:Inter,'Helvetica Neue',Arial,sans-serif;"
MARK = ('<div style="width:84px;height:92px;background:#173f30;color:#fff;display:grid;place-items:center;'
        'clip-path:polygon(0 0,100% 0,100% 75%,50% 100%,0 75%);font-size:60px;font-weight:500">&#10003;</div>')

title = f"""<html><body style="margin:0;width:1920px;height:1080px;background:#f4f6f2;{FONT}display:flex;align-items:center;justify-content:center">
<div style="width:1400px">
 <div style="display:flex;align-items:center;gap:26px">{MARK}<div style="font-size:84px;font-weight:750;letter-spacing:-3px;color:#14221b">VeriFix<span style="color:#2f7a55">.</span></div></div>
 <div style="font-size:76px;font-weight:650;letter-spacing:-2.6px;line-height:1.12;color:#173f30;margin-top:70px">Coding agents say &ldquo;fixed&rdquo;.<br>VeriFix has to prove it.</div>
 <div style="font-size:30px;color:#55665b;margin-top:44px">Team HyperX &middot; Shivansh Jain &middot; neatHack 2026</div>
 <div style="display:flex;gap:16px;margin-top:56px">{''.join(f'<span style="font-size:24px;padding:12px 22px;border:1px solid #cadbcb;border-radius:10px;background:#fff;color:#2b6645">{t}</span>' for t in ('neatlogs &middot; tracing','Entire &middot; graph + checkpoints','cfo.ai &middot; business plan','AWS Lambda &middot; live runs'))}</div>
</div></body></html>"""

close = f"""<html><body style="margin:0;width:1920px;height:1080px;background:#173f30;{FONT}display:flex;align-items:center;justify-content:center;color:#fff">
<div style="width:1400px">
 <div style="font-size:26px;letter-spacing:5px;color:#9fd1b3;font-weight:700">CHECK IT YOURSELF</div>
 <div style="font-size:80px;font-weight:650;letter-spacing:-2.8px;line-height:1.12;margin-top:30px">Every claim, verified live.</div>
 <div style="font-size:34px;margin-top:60px;line-height:1.9;color:#e4f1e8">
  <div><span style="color:#9fd1b3">Verify screen</span> &nbsp; shivanshjain456.github.io/neatHack/#verify</div>
  <div><span style="color:#9fd1b3">Source</span> &nbsp; github.com/shivanshjain456/neatHack</div>
 </div>
 <div style="font-size:26px;color:#9fd1b3;margin-top:60px">VeriFix &middot; Team HyperX &middot; #neatHack</div>
</div></body></html>"""


def label(text, sub="", where="bottom:44px"):
    sub_html = f'<div style="font-size:21px;color:#cfe5d6;margin-top:4px">{sub}</div>' if sub else ""
    return f"""<html><body style="margin:0;width:1920px;height:1080px;background:transparent;{FONT}">
<div style="position:absolute;left:50%;{where};white-space:nowrap;transform:translateX(-50%);background:rgba(23,63,48,.94);color:#fff;
padding:16px 30px;border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.18);text-align:center;max-width:1500px">
<div style="font-size:28px;font-weight:650;letter-spacing:-.3px">{text}</div>{sub_html}</div></body></html>"""


LABELS = {
    "l_verify": label("Verify screen &middot; 7 claims checked live", "GitHub API &middot; neatlogs MCP &middot; recorded runs"),
    "l_run": label("Live run on AWS Lambda &middot; real model call", "Controlled failure test: a bad first patch is injected on purpose"),
    "l_run2": label("Caller regression caught &rarr; workspace rolled back &rarr; attempt 2 verified"),
    "l_neat": label("neatlogs &middot; per-step traces of tokens, latency and cost"),
    "l_tokens": label("Total tokens per fix 31,093 &rarr; 946 (&minus;97%) &middot; latency 41.4 s &rarr; 1.48 s (&minus;96%)",
                      "Recorded experiment exp_24aa3f2776 &middot; ledger rounding benchmark", where="top:300px"),
    "l_entire": label("Entire &middot; Graph for caller context &middot; Checkpoints for build provenance"),
    "l_cfo": label("cfo.ai business plan &middot; projections, not realised results", "Recalculated from plan.xlsx formulas"),
    "l_oss": label("Open source &middot; neatlogs SDK issue #199 and pull request #203"),
}

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    for name, html in (("title", title), ("close", close)):
        pg.set_content(html)
        pg.screenshot(path=str(OUT / f"{name}.png"))
    for name, html in LABELS.items():
        pg.set_content(html)
        pg.screenshot(path=str(OUT / f"{name}.png"), omit_background=True)
    b.close()
print(sorted(x.name for x in OUT.iterdir()))
