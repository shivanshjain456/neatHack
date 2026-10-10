"""Deterministic boundary, API, database, packaging and property-based release gates.

Fault fixtures in this module are tests, never application fallbacks.
"""
from __future__ import annotations
import asyncio
import concurrent.futures
import json
import re
import subprocess
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st
from verifix.dashboard import WEB_DIR, build_dashboard
from verifix.http_boundary import HTTPBoundary, OPERATOR_PATHS, TokenBucket
from verifix.server import app, lambda_handler, RunRequest, GraphInspectRequest
from verifix.state_store import VeriFixStateStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    # Fresh per-test middleware state, no dependency mocking in API integration tests.
    app.middleware_stack = None
    with TestClient(app) as c:
        yield c


def test_js_syntax_and_single_source():
    subprocess.run(['node','--check',str(WEB_DIR/'app.js')],check=True,capture_output=True)
    assert (ROOT/'docs/index.html').read_text() == build_dashboard()
    assert 'INLINE_JS' not in build_dashboard()
    assert '<script src=' not in build_dashboard()
    assert 'window.fetch =' not in build_dashboard()


def test_html_ids_are_unique():
    ids = re.findall(r'\bid="([^"]+)"', (WEB_DIR/'index.html').read_text())
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize('path',['/','/api/health','/api/workspace'])
def test_api_smoke_and_headers(client,path):
    res=client.get(path)
    assert res.status_code==200
    assert res.headers['x-content-type-options']=='nosniff'
    assert 'object-src \'none\'' in res.headers['content-security-policy']
    assert "script-src 'sha256-" in res.headers['content-security-policy']
    assert res.headers['cache-control']=='no-store'


def test_workspace_schema_real_records(client):
    d=client.get('/api/workspace').json()
    assert d['schema_version']==1
    assert len(d['benchmarks'])==4
    assert d['runs'] and d['experiments']
    assert all('steps' not in r and 'verification_certificate_json' not in r for r in d['runs'])
    assert 'instance' in d['source']
    r=client.get('/api/runs/'+d['runs'][0]['run_id'])
    assert r.status_code==200
    assert r.json()['steps']
    assert 'blast_radius_json' not in r.json()
    assert r.json()['run_id']==d['runs'][0]['run_id']


@pytest.mark.parametrize('run_id',['missing_run_123','%3Cscript%3E','a'*129,"quoted%27id"])
def test_unknown_and_invalid_runs(client,run_id):
    assert client.get('/api/runs/'+run_id).status_code in (404,422)


@pytest.mark.parametrize('path',sorted(OPERATOR_PATHS))
def test_public_code_execution_closed(client,path):
    assert client.post(path,json={}).status_code==403
    assert client.post(path+'/',json={}).status_code==403


def test_wrong_token_is_denied(client,monkeypatch):
    monkeypatch.setenv('VERIFIX_OPERATOR_TOKEN','test-only-operator-token')
    assert client.post('/api/live-playground-fix',headers={'Authorization':'Bearer wrong'},json={}).status_code==403
    # Correct auth reaches request validation, NOT an unconditional success response.
    assert client.post('/api/live-playground-fix',headers={'Authorization':'Bearer test-only-operator-token'},json={}).status_code==422


@pytest.mark.parametrize('payload',[
    {'mode':'arbitrary'}, {'case_id':'../secret'}, {'case_id':'x'*101},
    {'mode':'graph_guarded','hidden_extra':'reject'}, {'case_id':None},
])
def test_invalid_run_inputs_do_not_execute(client,payload):
    assert client.post('/api/run',json=payload).status_code in (400,422)


def test_json_and_size_boundaries(client):
    assert client.post('/api/run',content='{',headers={'content-type':'application/json'}).status_code==422
    assert client.post('/api/run',content='a'*131073).status_code==413
    assert client.post('/api/resume',json={'run_id':'nonexistent'}).status_code==404


def test_completed_run_cannot_resume(client):
    d=client.get('/api/workspace').json()
    r=next(r for r in d['runs'] if r['status']=='VERIFIED_COMPLETE')
    assert client.post('/api/resume',json={'run_id':r['run_id']}).status_code==409


def test_cors_allowlist(client):
    h={'Origin':'https://shivanshjain456.github.io','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'}
    r=client.options('/api/run',headers=h)
    assert r.status_code==200
    assert r.headers['access-control-allow-origin']=='https://shivanshjain456.github.io'
    h['Origin']='https://untrusted.example'
    r=client.options('/api/run',headers=h)
    assert r.status_code==400 and 'access-control-allow-origin' not in r.headers


def test_request_rate_limit_and_retry_header(client):
    responses=[client.post('/api/run',json={'mode':'invalid'}) for _ in range(7)]
    assert [r.status_code for r in responses[:6]]==[422]*6
    assert responses[-1].status_code==429
    assert int(responses[-1].headers['retry-after'])>=1


def test_limiter_time_recovery_and_eviction():
    now=[0.0]
    bucket=TokenBucket(capacity=2,refill=1,max_clients=2,clock=lambda:now[0])
    assert bucket.acquire('a')==(True,0)
    assert bucket.acquire('a')==(True,0)
    assert bucket.acquire('a')==(False,1)
    now[0]=1
    assert bucket.acquire('a')==(True,0)
    bucket.acquire('b');bucket.acquire('c')
    assert len(bucket.clients)==2
    assert 'a' not in bucket.clients


def test_limiter_concurrent_atomicity():
    bucket=TokenBucket(capacity=10,refill=1,clock=lambda:0)
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        results=list(pool.map(lambda _:bucket.acquire('client')[0],range(100)))
    assert sum(results)==10


@given(st.lists(st.floats(min_value=0,max_value=100,allow_nan=False,allow_infinity=False),min_size=1,max_size=100))
@settings(max_examples=100)
def test_limiter_accounting_property(times):
    now=[0.0];bucket=TokenBucket(capacity=5,refill=2,clock=lambda:now[0])
    for ts in sorted(times):
        now[0]=ts;bucket.acquire('a')
        tokens,_=bucket.clients['a']
        assert 0<=tokens<=5


@given(st.text(max_size=180))
@settings(max_examples=100)
def test_symbol_boundary_fuzz(symbol):
    from pydantic import ValidationError
    try:
        v=GraphInspectRequest(symbol=symbol)
    except ValidationError:
        return
    assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*',v.symbol)
    assert len(v.symbol)<=128


def test_lambda_adapter_headers_and_real_data():
    app.middleware_stack=None
    event={'rawPath':'/api/workspace','requestContext':{'http':{'method':'GET','sourceIp':'adapter-test'}}}
    res=lambda_handler(event,None)
    assert res['statusCode']==200 and res['isBase64Encoded'] is False
    assert json.loads(res['body'])['runs']
    assert res['headers']['x-content-type-options']=='nosniff'


def test_sqlite_integrity_and_backup_restore(tmp_path):
    import sqlite3
    store=VeriFixStateStore(tmp_path/'isolated.db')
    backup=tmp_path/'restored.db'
    with sqlite3.connect(store.db_path) as src,sqlite3.connect(backup) as dst:
        src.backup(dst)
        assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert dst.execute('select count(*) from runs').fetchone()[0]==0
    restored=VeriFixStateStore(backup)
    assert restored.list_runs()==[]


def test_execution_lock_release_on_failure():
    # Explicit fault injection against a test-only ASGI dependency.
    calls=[]
    async def failing(scope,receive,send):
        calls.append(1)
        raise RuntimeError('injected dependency failure')
    boundary=HTTPBoundary(failing,build_dashboard())
    scope={'type':'http','path':'/api/run','method':'POST','headers':[],'client':('test',1)}
    async def receive(): return {'type':'http.request','body':b'{}','more_body':False}
    async def send(message): pass
    with pytest.raises(RuntimeError): asyncio.run(boundary(scope,receive,send))
    assert boundary.execution_lock.acquire(blocking=False)
    boundary.execution_lock.release()


def test_busy_execution_fails_fast():
    called=[];messages=[]
    async def target(scope,receive,send): called.append(True)
    boundary=HTTPBoundary(target,build_dashboard())
    scope={'type':'http','path':'/api/run','method':'POST','headers':[],'client':('test',1)}
    async def receive(): return {'type':'http.request','body':b'{}','more_body':False}
    async def send(message): messages.append(message)
    boundary.execution_lock.acquire()
    try: asyncio.run(boundary(scope,receive,send))
    finally: boundary.execution_lock.release()
    assert not called
    assert messages[0]['status']==409


def test_chunked_body_cap_without_content_length():
    messages=[]
    async def target(scope,receive,send): pytest.fail('oversized body reached application')
    boundary=HTTPBoundary(target,build_dashboard())
    scope={'type':'http','path':'/api/run','method':'POST','headers':[],'client':('test',1)}
    async def receive(): return {'type':'http.request','body':b'x'*70000,'more_body':True}
    async def send(message): messages.append(message)
    asyncio.run(boundary(scope,receive,send))
    assert messages[0]['status']==413


def test_sql_identifiers_are_allowlisted(tmp_path):
    store=VeriFixStateStore(tmp_path/'sql-boundary.db')
    with pytest.raises(ValueError):
        store.update_run('missing', **{'status = 1; DROP TABLE runs; --':'bad'})
    with pytest.raises(ValueError):
        store.update_run('missing', unknown_column='bad')
    assert store.list_runs()==[]
