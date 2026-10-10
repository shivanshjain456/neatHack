"""Small ASGI boundary, shared by uvicorn and the Lambda adapter.

Limits are process-local, not distributed quotas or a replacement for a WAF.
Only fixed benchmark execution is exposed without operator authentication.
"""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import threading
import time
from collections import OrderedDict

LOG = logging.getLogger(__name__)
OPERATOR_PATHS = frozenset({
    '/api/run-custom', '/api/auto-fix', '/api/live-playground-fix',
    '/api/experiment', '/api/dispatch-neatlogs-incident', '/api/entire-onboarding-qa',
})
EXECUTION_PATHS = OPERATOR_PATHS | {'/api/run', '/api/resume'}


class TokenBucket:
    """Bounded LRU buckets; monotonic clock and locked accounting."""
    def __init__(self, capacity=120, refill=2.0, max_clients=2048, clock=time.monotonic):
        if capacity < 1 or refill <= 0 or max_clients < 1:
            raise ValueError('Invalid token bucket configuration')
        self.capacity, self.refill, self.max_clients, self.clock = capacity, refill, max_clients, clock
        self.lock = threading.Lock()
        self.clients = OrderedDict()

    def acquire(self, key):
        now = self.clock()
        with self.lock:
            tokens, at = self.clients.pop(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + max(0, now-at)*self.refill)
            allowed = tokens >= 1
            retry = 0 if allowed else max(1, math.ceil((1-tokens)/self.refill))
            self.clients[key] = (tokens-1 if allowed else tokens, now)
            while len(self.clients) > self.max_clients:
                self.clients.popitem(last=False)
            return allowed, retry


class HTTPBoundary:
    def __init__(self, app, dashboard_html):
        import base64
        script = dashboard_html.split('<script>',1)[1].split('</script>',1)[0]
        digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        cloud = 'https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws'
        self.headers = [
            (b'x-content-type-options', b'nosniff'),
            (b'referrer-policy', b'strict-origin-when-cross-origin'),
            (b'permissions-policy', b'camera=(), microphone=(), geolocation=()'),
            (b'content-security-policy', f"default-src 'self'; script-src 'sha256-{digest}'; style-src 'self' 'unsafe-inline'; img-src 'self' data: {cloud}; connect-src 'self' {cloud}; object-src 'none'; base-uri 'none'; form-action 'none'".encode()),
            (b'cache-control', b'no-store'),
        ]
        self.app = app
        self.read_limiter = TokenBucket()
        self.write_limiter = TokenBucket(capacity=6, refill=1/30)
        self.execution_lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path, method = scope.get('path',''), scope.get('method','GET')
        headers = dict(scope.get('headers', []))
        async def secure_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + self.headers
            await send(message)
        async def reject(code, detail, extra=()):
            body = json.dumps({'detail': detail}).encode()
            await secure_send({'type':'http.response.start','status':code,'headers':[(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode()),*extra]})
            await send({'type':'http.response.body','body':body})
        # Never trust X-Forwarded-For supplied by a visitor. Lambda supplies sourceIp.
        client = (scope.get('client') or ('unknown',))[0]
        if method == 'POST' and path.rstrip('/') in OPERATOR_PATHS:
            token = os.environ.get('VERIFIX_OPERATOR_TOKEN','')
            auth = headers.get(b'authorization',b'').decode('latin-1')
            if not token or not hmac.compare_digest(auth, 'Bearer '+token):
                return await reject(403, 'Operator authentication required. Arbitrary code and custom repositories are not public sandbox operations.')
        if path.startswith('/api/') and method != 'OPTIONS':
            allowed, retry = (self.write_limiter if method=='POST' else self.read_limiter).acquire(client)
            if not allowed:
                return await reject(429,'Request limit reached. Retry later.',[(b'retry-after',str(retry).encode())])
        if method == 'POST':
            limit = 131072
            length = headers.get(b'content-length',b'0')
            try:
                if int(length) < 0 or int(length) > limit:
                    return await reject(413,'Request body exceeds 128 KiB.')
            except ValueError:
                return await reject(400,'Invalid Content-Length.')
            body = bytearray()
            while True:
                msg = await receive()
                if msg['type'] == 'http.disconnect':
                    return
                body.extend(msg.get('body',b''))
                if len(body)>limit:
                    return await reject(413,'Request body exceeds 128 KiB.')
                if not msg.get('more_body',False):
                    break
            sent = False
            original_receive = receive
            async def buffered_receive():
                nonlocal sent
                if not sent:
                    sent=True
                    return {'type':'http.request','body':bytes(body),'more_body':False}
                return await original_receive()
            receive = buffered_receive
        acquired = False
        if method == 'POST' and path.rstrip('/') in EXECUTION_PATHS:
            acquired = self.execution_lock.acquire(blocking=False)
            if not acquired:
                return await reject(409,'Another execution is active in this server instance. Check run history before retrying.')
        try:
            await self.app(scope,receive,secure_send)
        finally:
            if acquired:
                self.execution_lock.release()
