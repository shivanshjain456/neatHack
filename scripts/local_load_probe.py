"""Bounded local read-only load, spike/throttle and recovery probe; refuses remote hosts."""
import concurrent.futures
import json
import statistics
import time
from pathlib import Path
import httpx

URL='http://127.0.0.1:8000'
results=[]
with httpx.Client(timeout=20) as client:
 def one(i):
    t=time.perf_counter();r=client.get(URL+'/api/workspace');return {'status':r.status_code,'ms':round((time.perf_counter()-t)*1000,2),'bytes':len(r.content)}
 for phase,count,workers in [('baseline',10,1),('concurrent',30,8),('spike',160,32)]:
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        rows=list(pool.map(one,range(count)))
    accepted=[r['ms'] for r in rows if r['status']==200]
    results.append({'phase':phase,'requests':count,'concurrency':workers,'wall_s':round(time.perf_counter()-start,3),'statuses':{str(s):sum(r['status']==s for r in rows) for s in {r['status'] for r in rows}},'accepted_p50_ms':round(statistics.median(accepted),2) if accepted else None,'accepted_max_ms':max(accepted) if accepted else None})
    assert all(r['status'] in (200,429) for r in rows)
 # 30-second bounded soak/recovery, not a claim of long-duration endurance certification.
 start=time.perf_counter();soak=[]
 for i in range(30):
    time.sleep(1);soak.append(one(i))
 assert all(r['status']==200 for r in soak)
 results.append({'phase':'30-second-recovery-soak','requests':30,'statuses':{'200':30},'duration_s':round(time.perf_counter()-start,2),'max_ms':max(r['ms'] for r in soak)})
Path('artifacts/ui-release/local-load.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
