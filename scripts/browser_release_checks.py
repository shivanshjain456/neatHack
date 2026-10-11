"""Reproducible browser gates. Real reads + explicitly labeled fault fixtures.
No live model calls unless --live-run is explicitly passed.
"""
import argparse
import json
import os
import random
import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser()
parser.add_argument('--base',default='http://127.0.0.1:8000')
parser.add_argument('--output',default='artifacts/ui-release/browser-local.json')
parser.add_argument('--engines',default='chromium,firefox,webkit')
parser.add_argument('--live-run',action='store_true')
parser.add_argument('--faults',action='store_true')
a=parser.parse_args()
root=Path(__file__).resolve().parents[1]
checks=[];violations=[];errors=[];completed=False
def check(name,fn):
    start=time.perf_counter()
    try: fn();checks.append({'name':name,'passed':True,'ms':round((time.perf_counter()-start)*1000,1)})
    except Exception as exc: checks.append({'name':name,'passed':False,'error':str(exc)[:1500]});raise

def axe(page,label):
    page.evaluate(Path('/tmp/axe.min.js').read_text())
    result=page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
    found=[{'id':v['id'],'impact':v['impact'],'nodes':[n['target'] for n in v['nodes']]} for v in result['violations']]
    violations.append({'screen':label,'violations':found})
    assert not found, json.dumps(found)

def no_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal document overflow'

try:
 with sync_playwright() as p:
  for engine in a.engines.split(','):
   b=getattr(p,engine).launch()
   context=b.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
   context.tracing.start(screenshots=True,snapshots=True)
   page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
   response=page.goto(a.base,wait_until='networkidle');assert response.status==200
   expect(page.get_by_role('heading',name='A safer path from bug to fix.')).to_be_visible()
   ce=httpx.get(a.base+'/api/workspace',timeout=30).json()['controlled_experiment'];g_tok=round(ce['arms']['graph_guarded']['mean_total_tokens']);b_tok=round(ce['arms']['baseline_naive']['mean_total_tokens'])
   check(engine+': overview shows controlled experiment from API',lambda:expect(page.locator('.metrics')).to_contain_text(f'{g_tok:,} vs. {b_tok:,} tokens per fix'))
   check(engine+': overview accessibility',lambda:axe(page,engine+' overview'))
   if engine=='chromium':page.screenshot(path=str(root/'artifacts/ui-release/after-desktop.png'),full_page=True)
   page.get_by_role('button',name='Inspect patch').click()
   expect(page.get_by_role('heading',name='Patch diff')).to_be_visible()
   check(engine+': inspector accessibility',lambda:axe(page,engine+' inspector'))
   for _ in range(12):
    page.keyboard.press('Tab');assert page.evaluate("document.querySelector('#run-dialog').contains(document.activeElement)")
   check(engine+': dialog focus containment',lambda:None)
   if engine=='chromium':page.screenshot(path=str(root/'artifacts/ui-release/inspector.png'))
   page.keyboard.press('Escape');expect(page.locator('#run-dialog')).not_to_be_visible()
   check(engine+': dialog Escape closes',lambda:expect(page.get_by_role('button',name='Inspect patch')).to_be_focused())
   for route,label in [('runs','Run history'),('benchmarks','Run a benchmark'),('evidence','Evidence library'),('system','System & quality')]:
    page.locator(f'nav [data-route="{route}"]').click()
    check(engine+': '+route+' accessibility',lambda:axe(page,engine+' '+route))
    if route=='runs':
     page.get_by_label('Find a run').fill('nothing-matches-123');expect(page.get_by_role('heading',name='No matching runs')).to_be_visible()
     page.get_by_role('button',name='Clear filters').click();expect(page.locator('#run-rows tr').first).to_be_visible()
     check(engine+': filter empty and recovery',lambda:None)
    if route=='benchmarks':
     page.get_by_role('button',name='Review & run benchmark').click();expect(page.get_by_role('heading',name='Start a live benchmark?')).to_be_visible()
     check(engine+': execution confirmation accessibility',lambda:axe(page,engine+' confirmation'))
     page.get_by_role('button',name='Cancel',exact=True).click();expect(page.locator('#confirm-dialog')).not_to_be_visible()
    if route=='evidence':
     for tab in ['Entire','Financial model','Open source','neatlogs']:
      page.get_by_role('button',name=tab,exact=True).click()
      check(engine+': evidence '+tab+' accessibility',lambda:axe(page,engine+' '+tab))
   for width in [320,390,768,1280,1440]:
    page.set_viewport_size({'width':width,'height':844})
    for route in ['overview','runs','benchmarks','evidence','system']:
     page.evaluate(f"location.hash='{route}'")
     expect(page.locator('#breadcrumb')).to_have_text({'overview':'Overview','runs':'Run history','benchmarks':'Run a benchmark','evidence':'Evidence library','system':'System & quality'}[route])
     check(engine+f': {route} no overflow at {width}px',lambda:no_overflow(page))
    if width==390 and engine=='chromium':
     page.evaluate("location.hash='overview'");expect(page.locator('.hero')).to_be_visible();page.screenshot(path=str(root/'artifacts/ui-release/after-mobile.png'),full_page=True)
   random.seed(10)
   for route in random.choices(['overview','runs','benchmarks','evidence','system'],k=25):
    page.evaluate(f"location.hash='{route}'")
   check(engine+': repeated navigation no script errors',lambda:(_ for _ in ()).throw(AssertionError(errors)) if errors else None)
   context.tracing.stop(path=str(root/f'artifacts/ui-release/{engine}-browser-trace.zip'))
   context.close();b.close()
  if a.faults:
   b=p.chromium.launch();fixture=httpx.get(a.base+'/api/workspace',timeout=30).json()
   def fault(name,status=200,body=None,abort=False):
    ctx=b.new_context();page=ctx.new_page()
    def handler(route):
     if abort:route.abort('failed')
     else:route.fulfill(status=status,content_type='application/json',body=body)
    page.route('**/api/workspace',handler);page.goto(a.base)
    expect(page.get_by_role('heading',name='The workspace could not connect.')).to_be_visible()
    check('fault fixture: '+name,lambda:expect(page.get_by_role('button',name='Retry connection',exact=True)).to_be_visible())
    page.unroute('**/api/workspace',handler);page.get_by_role('button',name='Retry connection',exact=True).click()
    expect(page.get_by_role('heading',name='A safer path from bug to fix.')).to_be_visible();check('fault recovery: '+name,lambda:None);ctx.close()
   fault('503',503,'{"detail":"injected"}');fault('429',429,'{"detail":"injected"}');fault('invalid JSON',200,'<html>not-json</html>');fault('malformed schema',200,'{}');fault('network unavailable',abort=True)
   ctx=b.new_context();page=ctx.new_page()
   empty={'runs':[],'experiments':[],'benchmarks':[]}
   page.route('**/api/workspace',lambda r:r.fulfill(json=empty));page.goto(a.base);expect(page.get_by_role('heading',name='No verified runs yet')).to_be_visible();expect(page.locator('main')).to_contain_text('controlled experiment file is not included')
   assert 'NaN' not in page.locator('body').inner_text();check('empty fixture: missing metrics not fabricated',lambda:None);ctx.close()
   ctx=b.new_context();page=ctx.new_page();hostile=json.loads(json.dumps(fixture));hostile['runs'][0]['target_symbol']='<img src=x onerror="window.pwned=1">'
   page.route('**/api/workspace',lambda r:r.fulfill(json=hostile));page.goto(a.base+'/#runs');expect(page.locator('#run-rows')).to_contain_text('<img src=x');assert page.evaluate('window.pwned') is None
   check('security fixture: stored XSS escaped',lambda:None);ctx.close()
   ctx=b.new_context(locale='de-DE');page=ctx.new_page();page.goto(a.base);_ce=fixture['controlled_experiment'];expect(page.locator('.metrics')).to_contain_text(f"{round(_ce['arms']['baseline_naive']['mean_total_tokens']):,}".replace(',','.'))
   check('locale: de-DE numeric formatting',lambda:None);ctx.close()
   ctx=b.new_context(java_script_enabled=False);page=ctx.new_page();page.goto(a.base);expect(page.locator('.noscript')).to_contain_text('JavaScript is required');check('no JavaScript: honest fallback link',lambda:None);ctx.close()
   # Read-only volume fixture, clearly not claimed as observed production scale.
   ctx=b.new_context();page=ctx.new_page();volume=json.loads(json.dumps(fixture));volume['runs']=(fixture['runs']*100)[:1000]
   page.route('**/api/workspace',lambda r:r.fulfill(json=volume));t=time.perf_counter();page.goto(a.base+'/#runs');expect(page.locator('#run-rows tr')).to_have_count(10)
   page.get_by_label('Find a run').fill('nomatch');expect(page.get_by_role('heading',name='No matching runs')).to_be_visible();assert time.perf_counter()-t<5
   check('volume fixture: 1000 records paginated and searchable under 5s',lambda:None);ctx.close();b.close()
  if a.live_run:
   b=p.chromium.launch();page=b.new_page();page.goto(a.base+'/#benchmarks')
   expect(page.get_by_role('button',name='Review & run benchmark')).to_be_visible()
   page.get_by_role('button',name='Review & run benchmark').click();page.get_by_role('button',name='Confirm & run').click()
   expect(page.locator('#run-result')).to_contain_text('Verified',timeout=190000)
   page.get_by_role('button',name='Inspect run evidence').click();expect(page.locator('.diff')).not_to_contain_text('No final patch')
   page.screenshot(path=str(root/'artifacts/ui-release/live-run-verified.png'),full_page=True)
   checks.append({'name':'LIVE model benchmark → verified outcome → nonempty patch inspector','passed':True,'evidence':page.locator('#run-detail').inner_text()[:3000]})
   b.close()
 completed=True
finally:
 out={'completed':completed,'base':a.base,'checks':checks,'passed':sum(x['passed'] for x in checks),'total':len(checks),'axe_results':violations,'page_errors':errors,'fault_fixtures_enabled':a.faults}
 Path(a.output).write_text(json.dumps(out,indent=2));print(json.dumps({'passed':out['passed'],'total':out['total'],'page_errors':errors,'report':a.output}))
