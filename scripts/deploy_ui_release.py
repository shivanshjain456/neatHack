"""Deploy audited source with a saved rollback package and post-deploy HTTP gates.

Requires preinstalled cp312 Linux dependencies in --dependencies. Packages only
runtime credentials; no GitHub token or AWS long-lived key is shipped to Lambda.
Never upload either deployment zip or rollback zip to public artifact storage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import zipfile
import boto3
import httpx
from verifix.config import load_env_if_present
from verifix.dashboard import build_dashboard

p=argparse.ArgumentParser()
p.add_argument('--dependencies',default='/home/user/.cache/lambda-release')
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
private=Path('/home/user/.cache/verifix-deployment');private.mkdir(parents=True,exist_ok=True);private.chmod(0o700)
load_env_if_present()
name='verifix-hyperx-mission-control'
base='https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws'
lam=boto3.client('lambda',region_name='us-east-1')
previous=lam.get_function(FunctionName=name)
rollback=private/'rollback.zip'
r=httpx.get(previous['Code']['Location'],timeout=60);r.raise_for_status();rollback.write_bytes(r.content);rollback.chmod(0o600)
package=private/'release.zip'
html=build_dashboard();(root/'docs/index.html').write_text(html)
import subprocess
import sys
sys.path.insert(0,str(root/'scripts'))
from verifix import supply_chain as sc
entries=[]
deps=Path(a.dependencies)
if not (deps/'fastapi').is_dir():raise RuntimeError('Missing runtime dependencies')
for f in sorted(deps.rglob('*')):
    if f.is_file() and '__pycache__' not in f.parts:entries.append((str(f.relative_to(deps)),f.read_bytes()))
for f in sorted((root/'src/verifix').rglob('*')):
    if f.is_file() and '__pycache__' not in f.parts:entries.append(('verifix/'+str(f.relative_to(root/'src/verifix')),f.read_bytes()))
for sub in ['benchmarks','scripts','docs','.entire','quality']:
    for f in sorted((root/sub).rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and '.pytest_cache' not in f.parts and '.git' not in f.parts:entries.append((str(f.relative_to(root)),f.read_bytes()))
for name_ in ['README.md','hackathon.md','BUSINESS_PLAN.md','REAL_OSS_BUG_REPORT_NEATLOGS.md','plan.xlsx','QUALITY_REPORT.md','requirements-runtime.lock','requirements-runtime.hashes.lock']:
    f=root/name_
    if f.exists():entries.append((name_,f.read_bytes()))
# Reproducible code bundle + SLSA provenance, verified before anything is uploaded.
code_bundle=private/'code-bundle.zip'
code_sha=sc.deterministic_zip(code_bundle,entries)
commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
dirty=subprocess.run(['git','status','--porcelain','--','src','scripts','requirements-runtime.lock','requirements-runtime.hashes.lock'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
if dirty:raise RuntimeError('Refusing to deploy: tracked source differs from commit '+commit[:12])
materials={'file:'+n:sc.sha256_file(root/n) for n in ['requirements-runtime.lock','requirements-runtime.hashes.lock']}
statement=sc.provenance_statement('code-bundle.zip',code_sha,commit,'https://github.com/shivanshjain456/neatHack',materials,'https://github.com/shivanshjain456/neatHack/local-operator','deploy-'+str(int(time.time())))
problems=sc.verify_provenance(statement,code_bundle,commit,materials)
if problems:raise RuntimeError('Provenance verification failed: '+'; '.join(problems))
(root/'artifacts/supply-chain').mkdir(parents=True,exist_ok=True)
(root/'artifacts/supply-chain/deploy-provenance.intoto.json').write_text(json.dumps(statement,indent=1)+'\n')
# Lambda uses its execution role for AWS. Operator token remains server-side only (never in the attested bundle).
keys=['LITELLM_API_KEY','LITELLM_BASE_URL','NEATLOGS_API_KEY','NEATLOGS_ENDPOINT','GEMINI_API_KEY','OPENROUTER_API_KEY','TOKENHARBOR_API_KEY','VERIFIX_OPERATOR_TOKEN']
env='\n'.join(k+'='+os.environ[k] for k in keys if os.environ.get(k))+'\n'
sc.deterministic_zip(package,entries+[('.verifix_secrets.env',env.encode())])
package.chmod(0o600)
report={'function':name,'code_bundle_sha256':code_sha,'commit':commit,'provenance_verified':True,'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'package_bytes':package.stat().st_size,'rollback_sha256':hashlib.sha256(rollback.read_bytes()).hexdigest(),'checks':[]}
try:
    lam.update_function_code(FunctionName=name,ZipFile=package.read_bytes())
    lam.get_waiter('function_updated').wait(FunctionName=name)
    with httpx.Client(timeout=60) as c:
        response=c.get(base+'/');assert response.status_code==200
        assert hashlib.sha256(response.content).hexdigest()==report['html_sha256']
        report['checks'].append('Live HTML byte-for-byte matches local generated artifact')
        r=c.get(base+'/api/workspace');assert r.status_code==200 and r.json()['runs']
        report['workspace_bytes']=len(r.content);report['checks'].append('Workspace returns recorded run data')
        r=c.post(base+'/api/live-playground-fix',json={});assert r.status_code==403
        report['checks'].append('Anonymous arbitrary-code execution denied')
        assert c.get(base+'/api/health').json()['status']=='ok'
        r=c.get(base+'/api/judge-proof');assert r.status_code==200 and len(r.json()['items'])==7
        report['judge_proof_summary']=r.json()['summary'];report['checks'].append('Judge verification endpoint returns all 7 checklist items')
        report['checks'].append('Health endpoint responds')
    report['status']='deployed_and_smoke_verified'
except Exception:
    report['status']='failed_rolled_back'
    lam.update_function_code(FunctionName=name,ZipFile=rollback.read_bytes())
    lam.get_waiter('function_updated').wait(FunctionName=name)
    raise
finally:
    (root/'artifacts/ui-release/deployment.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
