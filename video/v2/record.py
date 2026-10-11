"""Record demo scenes from the live deployment with Playwright.

Every scene is a real browser session against the live Lambda URL. Timestamps of key
on-screen events are written to scenes.json so narration can be aligned to them.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws"
OUT = Path(__file__).parent / "raw"
OUT.mkdir(exist_ok=True)
VIEW = {"width": 1440, "height": 810}
REC = VIEW

CURSOR = """
window.addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.id = '__demo_cursor';
  c.style.cssText = 'position:fixed;left:0;top:0;width:18px;height:18px;border-radius:50%;'
    + 'background:rgba(30,80,60,.35);border:2px solid #1e503c;pointer-events:none;z-index:2147483647;'
    + 'transform:translate(-50%,-50%);transition:width .12s,height .12s';
  document.body.appendChild(c);
  document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  document.addEventListener('mousedown', () => { c.style.width = c.style.height = '12px'; }, true);
  document.addEventListener('mouseup', () => { c.style.width = c.style.height = '18px'; }, true);
});
"""

meta = {}


class Scene:
    def __init__(self, p, name):
        self.name = name
        self.browser = p.chromium.launch()
        self.ctx = self.browser.new_context(viewport=VIEW, record_video_dir=str(OUT / name), record_video_size=REC,
                                            reduced_motion="no-preference")
        self.ctx.add_init_script(CURSOR)
        self.page = self.ctx.new_page()
        self.t0 = time.perf_counter()
        self.marks = {}
        self.mouse = (720, 400)

    def mark(self, key):
        self.marks[key] = round(time.perf_counter() - self.t0, 3)

    def move_to(self, locator, steps=25):
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(x, y, steps=steps)
        self.mouse = (x, y)
        time.sleep(0.25)

    def click(self, locator):
        self.move_to(locator)
        self.page.mouse.down()
        time.sleep(0.08)
        self.page.mouse.up()

    def scroll(self, total, step=60, pause=0.03):
        self.page.mouse.move(*self.mouse)
        done = 0
        while abs(done) < abs(total):
            d = step if total > 0 else -step
            self.page.mouse.wheel(0, d)
            done += d
            time.sleep(pause)

    def close(self):
        self.mark("end")
        video = self.page.video
        self.ctx.close()
        path = Path(video.path())
        target = OUT / f"{self.name}.webm"
        path.replace(target)
        self.browser.close()
        meta[self.name] = {"file": str(target), **self.marks}
        print(self.name, meta[self.name], flush=True)


def scene_verify(p):
    s = Scene(p, "s2_verify")
    s.page.goto(BASE + "/#verify", wait_until="domcontentloaded")
    expect(s.page.locator(".proof-card")).to_have_count(7, timeout=60000)
    time.sleep(0.6)
    s.mark("ready")
    s.page.mouse.move(700, 300, steps=10)
    time.sleep(1.5)
    s.scroll(900, step=40, pause=0.05)
    time.sleep(1.2)
    s.scroll(900, step=40, pause=0.05)
    time.sleep(1.2)
    s.move_to(s.page.locator(".proof-card", has_text="The agent recovers from failures").get_by_role("link", name="Reproduce it live"))
    time.sleep(2.5)
    s.close()


def scene_run(p):
    s = Scene(p, "s3_run")
    page = s.page
    page.goto(BASE + "/#benchmarks", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Review & run benchmark")).to_be_visible(timeout=60000)
    time.sleep(0.6)
    s.mark("ready")
    s.move_to(page.locator(".case-option").first)
    time.sleep(2.5)
    s.click(page.locator("summary", has_text="Advanced · controlled failure tests"))
    time.sleep(1.2)
    s.click(page.locator("#trap"))
    time.sleep(1.5)
    s.click(page.get_by_role("button", name="Review & run benchmark"))
    time.sleep(1.8)
    s.click(page.get_by_role("button", name="Confirm & run"))
    s.mark("run_started")
    expect(page.locator("#run-result")).to_contain_text("Verified", timeout=190000)
    s.mark("verified")
    page.locator("#run-result").scroll_into_view_if_needed()
    time.sleep(3.0)
    s.click(page.get_by_role("button", name="Inspect run evidence"))
    expect(page.locator("#run-dialog")).to_be_visible()
    s.mark("inspector")
    time.sleep(2.0)
    dialog = page.locator("#run-dialog")
    box = dialog.bounding_box()
    s.mouse = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(4):
        s.scroll(300, step=30, pause=0.05)
        time.sleep(1.4)
    meta["run_text"] = page.locator("#run-detail").inner_text()[:4000]
    time.sleep(1.0)
    s.close()


def evidence(s, tab):
    page = s.page
    s.click(page.get_by_role("button", name=tab))
    time.sleep(1.0)


def scene_neatlogs(p):
    s = Scene(p, "s5_neatlogs")
    page = s.page
    page.goto(BASE + "/#evidence", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="neatlogs")).to_be_visible(timeout=60000)
    time.sleep(0.6)
    s.mark("ready")
    evidence(s, "neatlogs")
    time.sleep(2.5)
    s.scroll(400, step=30, pause=0.05)
    time.sleep(4.0)
    s.click(page.locator('nav [data-route="overview"]'))
    expect(page.locator(".metric").first).to_be_visible(timeout=30000)
    s.mark("overview")
    page.locator(".metric").first.scroll_into_view_if_needed()
    time.sleep(1.0)
    s.move_to(page.locator(".metric").first)
    time.sleep(5.5)
    s.move_to(page.locator(".metric").nth(1))
    time.sleep(5.5)
    s.close()


def scene_entire(p):
    s = Scene(p, "s6_entire")
    page = s.page
    page.goto(BASE + "/#evidence", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Entire")).to_be_visible(timeout=60000)
    time.sleep(0.6)
    s.mark("ready")
    evidence(s, "Entire")
    time.sleep(2.5)
    s.scroll(400, step=30, pause=0.05)
    time.sleep(2.0)
    links = page.get_by_role("link", name="Inspect provenance")
    if links.count():
        s.move_to(links.first)
    time.sleep(3.0)
    s.scroll(400, step=30, pause=0.05)
    time.sleep(3.0)
    s.close()


def scene_cfo(p):
    s = Scene(p, "s7_cfo")
    page = s.page
    page.goto(BASE + "/#evidence", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Financial model")).to_be_visible(timeout=60000)
    time.sleep(0.6)
    s.mark("ready")
    evidence(s, "Financial model")
    expect(page.locator("#screen")).to_contain_text("Break-even in month")
    time.sleep(1.0)
    s.scroll(250, step=25, pause=0.05)
    s.move_to(page.locator("td", has_text="$433,928"))
    time.sleep(4.5)
    s.scroll(450, step=25, pause=0.05)
    s.move_to(page.locator("tr", has_text="Downside").locator("td").nth(2))
    time.sleep(5.5)
    s.close()


def scene_oss(p):
    s = Scene(p, "s8_oss")
    page = s.page
    page.goto(BASE + "/#evidence", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Open source")).to_be_visible(timeout=60000)
    time.sleep(0.6)
    s.mark("ready")
    evidence(s, "Open source")
    time.sleep(3.0)
    page.goto("https://github.com/neatlogs/neatlogs/pull/203", wait_until="domcontentloaded")
    expect(page.locator("h1").first).to_be_visible(timeout=30000)
    time.sleep(1.0)
    s.mark("github")
    s.mouse = (720, 400)
    time.sleep(2.5)
    s.scroll(500, step=25, pause=0.05)
    time.sleep(4.0)
    s.close()


SCENES = {"verify": scene_verify, "run": scene_run, "neatlogs": scene_neatlogs, "entire": scene_entire,
          "cfo": scene_cfo, "oss": scene_oss}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SCENES)
    meta_path = OUT / "scenes.json"
    if meta_path.exists():
        meta.update(json.loads(meta_path.read_text()))
    with sync_playwright() as p:
        for name in wanted:
            SCENES[name](p)
            meta_path.write_text(json.dumps(meta, indent=1))
