"""Browser gates for the judge Verify screen (real API reads; one explicitly labelled fault fixture).

Usage: python scripts/browser_verify_checks.py --base http://127.0.0.1:8000 [--engines chromium,firefox,webkit]
Needs /tmp/axe.min.js (axe-core) for the accessibility gate.
"""
import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:8000")
parser.add_argument("--api", default="", help="API origin when it differs from --base (e.g. Pages -> Lambda)")
parser.add_argument("--output", default="artifacts/ui-release/browser-verify.json")
parser.add_argument("--engines", default="chromium")
parser.add_argument("--screenshots", default="artifacts/ui-release/verify-screens")
a = parser.parse_args()
api_base = a.api or a.base
root = Path(__file__).resolve().parents[1]
shots = root / a.screenshots
shots.mkdir(parents=True, exist_ok=True)
checks, errors = [], []


def check(name, fn):
    start = time.perf_counter()
    try:
        fn()
        checks.append({"name": name, "passed": True, "ms": round((time.perf_counter() - start) * 1000, 1)})
    except Exception as exc:
        checks.append({"name": name, "passed": False, "error": str(exc)[:1500]})
        raise


def axe(page):
    page.evaluate(Path("/tmp/axe.min.js").read_text())
    result = page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
    found = [{"id": v["id"], "impact": v["impact"], "nodes": [n["target"] for n in v["nodes"]][:5]} for v in result["violations"]]
    assert not found, json.dumps(found)


def cards(page):
    return page.locator(".proof-card")


status = "failed"
try:
    with sync_playwright() as p:
        for engine in a.engines.split(","):
            browser = getattr(p, engine).launch()
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            tag = engine + ": "

            def first_load():
                page.goto(a.base + "/#verify", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name="Verify every claim in two minutes.")).to_be_visible()
                expect(cards(page)).to_have_count(7, timeout=40000)
                expect(page.locator('nav [data-route="verify"]')).to_have_attribute("aria-current", "page")
            check(tag + "verify screen loads all 7 checklist items from the live endpoint", first_load)

            def summary_consistent():
                api = page.request.get(api_base + "/api/judge-proof").json()
                shown = [int(x) for x in page.locator(".proof-summary strong").all_inner_texts()]
                assert shown == [api["summary"]["verified"], api["summary"]["attention"], api["summary"]["unavailable"]], (shown, api["summary"])
                titles = page.locator(".proof-card h2").all_inner_texts()
                assert titles == [i["criterion"] for i in api["items"]], titles
                badges = page.locator(".proof-card .badge-row .tag:first-child").all_inner_texts()
                expected = {"verified": "Verified", "attention": "Not met", "unavailable": "Source unavailable"}
                for badge, item in zip(badges, api["items"]):
                    assert expected[item["verdict"]] in badge, (badge, item["verdict"])
            check(tag + "summary counts, titles and verdict badges match the API response", summary_consistent)

            def history_card():
                card = page.locator(".proof-card", has_text="The build history is public")
                expect(card).to_contain_text("public commits")
                expect(card.locator(".tag").first).to_contain_text("Verified")
                expect(page.locator("#screen")).not_to_contain_text("judgement")
            check(tag + "commit-history card reports the public history as verified", history_card)

            check(tag + "verify screen accessibility (axe WCAG 2.1 AA)", lambda: axe(page))
            page.screenshot(path=str(shots / f"{engine}-verify-desktop.png"), full_page=True)

            def inspect_run():
                card = page.locator(".proof-card", has_text="The agent recovers from failures")
                card.get_by_role("button", name="Inspect this run").click()
                dialog = page.locator("#run-dialog")
                expect(dialog).to_be_visible()
                expect(dialog).to_contain_text("run_graph_case_01_le_", timeout=20000)
                expect(dialog).to_contain_text("rollbacks")
                page.screenshot(path=str(shots / f"{engine}-verify-inspector.png"))
                page.keyboard.press("Escape")
                expect(dialog).to_be_hidden()
            check(tag + "recovery card opens the recorded run in the inspector", inspect_run)

            def reproduce_link():
                page.locator(".proof-card", has_text="The agent recovers from failures").get_by_role("link", name="Reproduce it live").click()
                expect(page).to_have_url(a.base + "/#benchmarks")
                expect(page.locator("#trap")).to_be_attached()
            check(tag + "'Reproduce it live' goes to the benchmark runner with the caller trap", reproduce_link)

            def external_links_safe():
                page.goto(a.base + "/#verify")
                expect(cards(page)).to_have_count(7, timeout=40000)
                links = page.locator(".proof-card a[target=_blank]")
                assert links.count() >= 8
                for i in range(links.count()):
                    link = links.nth(i)
                    assert link.get_attribute("href").startswith("https://"), link.get_attribute("href")
                    assert "noopener" in link.get_attribute("rel")
            check(tag + "every external evidence link is https with rel=noopener", external_links_safe)

            def overview_banner():
                page.goto(a.base + "/#overview")
                page.get_by_role("link", name="Verify in 2 minutes →").click()
                expect(page).to_have_url(a.base + "/#verify")
                expect(cards(page)).to_have_count(7, timeout=40000)
            check(tag + "overview banner leads newcomers to the verify screen", overview_banner)

            def failure_and_retry():
                fresh = context.new_page()
                fresh.on("pageerror", lambda e: errors.append(str(e)))
                # Labelled fault fixture: the endpoint is forced to fail to prove the error state is honest.
                fresh.route("**/api/judge-proof", lambda route: route.fulfill(status=503, content_type="application/json",
                                                                              body='{"detail":"fault fixture: upstream unavailable"}'))
                fresh.goto(a.base + "/#verify")
                expect(fresh.get_by_role("heading", name="Verification could not run.")).to_be_visible(timeout=20000)
                expect(fresh.locator(".proof-card")).to_have_count(0)
                fresh.screenshot(path=str(shots / f"{engine}-verify-error.png"))
                fresh.unroute("**/api/judge-proof")
                fresh.get_by_role("button", name="Run the checks").click()
                expect(fresh.locator(".proof-card")).to_have_count(7, timeout=40000)
                fresh.close()
            check(tag + "endpoint failure shows an honest error with no fake cards, and retry recovers", failure_and_retry)

            def responsive():
                for width in (320, 390, 768, 1024):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.goto(a.base + "/#verify")
                    expect(cards(page)).to_have_count(7, timeout=40000)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"overflow at {width}px"
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(shots / f"{engine}-verify-mobile.png"), full_page=True)
            check(tag + "no horizontal overflow at 320/390/768/1024 px", responsive)

            def finance_matches_workbook():
                page.set_viewport_size({"width": 1440, "height": 1000})
                ws = page.request.get(api_base + "/api/workspace").json()
                plan = ws["plan_projection"]
                assert plan and len(plan["milestones"]) == 4, plan
                page.goto(a.base + "/#evidence", wait_until="domcontentloaded")
                page.get_by_role("button", name="Financial model").click()
                screen = page.locator("#screen")
                expect(screen).to_contain_text(f"Break-even in month {plan['first_positive_ebitda_month']}", timeout=20000)
                for m in plan["milestones"]:
                    expect(screen).to_contain_text(f"${round(m['arr']):,}")
                expect(screen).not_to_contain_text("$-")
                for stale in ("Infinite", "298,050", "Month 4"):
                    expect(screen).not_to_contain_text(stale)
                axe(page)
                page.screenshot(path=str(shots / f"{engine}-finance.png"), full_page=True)
            check(tag + "financial view shows the recalculated plan.xlsx milestones and no stale figures", finance_matches_workbook)

            assert not errors, errors
            browser.close()
    status = "passed"
finally:
    out = root / a.output
    out.write_text(json.dumps({"status": status, "base": a.base, "passed": sum(c["passed"] for c in checks),
                               "total": len(checks), "page_errors": errors, "checks": checks}, indent=2))
    print(json.dumps({"status": status, "passed": sum(c["passed"] for c in checks), "total": len(checks), "page_errors": errors}))
