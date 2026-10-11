'use strict';
(() => {
  const CLOUD = 'https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws';
  const API = location.hostname === 'shivanshjain456.github.io' || location.protocol === 'file:' ? CLOUD : '';
  const SOURCE = 'https://github.com/shivanshjain456/neatHack';
  const RAW = 'https://raw.githubusercontent.com/shivanshjain456/neatHack/main/';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const num = (value, digits = 0) => finite(value) ? new Intl.NumberFormat(undefined, {maximumFractionDigits:digits}).format(Number(value)) : '—';
  const sec = value => finite(value) ? `${num(value / 1000, 2)} s` : '—';
  const money = value => finite(value) ? '$' + num(value, 6) : '—';
  const isoDate = value => { const d = new Date(value); return value && !Number.isNaN(d.getTime()) ? d.toLocaleString(undefined, {dateStyle:'medium',timeStyle:'short'}) : 'Date unavailable'; };
  const time = value => finite(value) ? new Date(value * 1000).toLocaleString(undefined, {dateStyle:'medium',timeStyle:'short'}) : 'Date unavailable';
  const pretty = data => esc(JSON.stringify(data, null, 2));
  const paths = {verify:'<path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z"/><path d="m9 12 2 2 4-4"/>',overview:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',runs:'<path d="M5 6h14M5 12h14M5 18h14"/>',play:'<path d="m9 5 11 7-11 7Z"/>',evidence:'<path d="M5 3h10l4 4v14H5Z M14 3v5h5M8 12h8M8 16h6"/>',system:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',refresh:'<path d="M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3"/>',code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-16-2 20"/>',close:'<path d="m6 6 12 12M6 18 18 6"/>',check:'<path d="m5 12 4 4L19 6"/>'};
  function icon(name) { return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.evidence}</svg>`; }
  function icons() { document.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); }); }
  const titles = {verify:'Verify in 2 minutes',overview:'Overview',runs:'Run history',benchmarks:'Run a benchmark',evidence:'Evidence library',system:'System & quality'};
  const cases = {case_01_ledger_rounding:['Ledger rounding','Preserve integer precision and settlement contracts.'],case_02_ratelimiter_state:['Rate limiter','Repair shared state without breaking callers.'],case_03_webhook_validator:['Webhook validation','Check validation behavior and downstream contracts.'],case_04_dag_scheduler:['DAG scheduler','Repair scheduling while preserving dependency behavior.']};
  const S = {data:null,route:'overview',loading:false,error:null,loadedAt:null,filter:'',status:'all',page:1,caseId:'case_01_ledger_rounding',evidence:'neatlogs',running:false,result:null,runError:null,diagnostic:null,diagnosticBusy:false};
  let inspectionVersion = 0;
  function status(value) {
    const ok = value === 'VERIFIED_COMPLETE' || value === 'COMPLETED' || value === 'PASSED';
    const label = ({VERIFIED_COMPLETE:'Verified',INTERRUPTED_CHECKPOINTED:'Checkpointed',FAILED:'Failed',COMPLETED:'Completed',BLOCKED:'Blocked',NOT_REPRODUCED:'Not reproduced',RECOVERED:'Recovered',FAILED_MAX_ATTEMPTS:'Attempts exhausted'})[value] || String(value || 'Unknown').replaceAll('_',' ').toLowerCase();
    return `<span class="tag ${ok?'success':/FAIL|ERROR/.test(value||'')?'fail':'warn'}">${ok?'✓ ':''}${esc(label)}</span>`;
  }
  const KIND = [['ASSURANCE','Assurance'],['FAULT_LOCALIZATION','Fault localisation'],['SECURITY','Security'],['RECOVERY_ROLLBACK','Rollback'],['VERIFYING','Caller check']];
  function stepDetail(s) {
    const o = (s && typeof s.output === 'object' && s.output) || {};
    const phase = String(s?.phase || '');
    const k = KIND.find(([prefix]) => phase.startsWith(prefix));
    const kind = k ? `<span class="tag">${esc(k[1])}</span> ` : '';
    let body = '';
    if (s?.span_kind === 'ASSURANCE' && o.gates && typeof o.gates === 'object') {
      const chips = Object.entries(o.gates).map(([g,st]) => `<span class="tag ${st==='pass'?'success':st==='fail'?'fail':'warn'}">${esc(g)} ${st==='pass'?'✓':st==='fail'?'✕':'!'}</span>`).join('');
      const metrics = [o.strength?`strength ${esc(o.strength)}`:'', Number.isFinite(o.mutation_score)?`mutation ${Number(o.mutation_score).toFixed(2)}`:'', Number.isFinite(o.diff_coverage)?`diff coverage ${Number(o.diff_coverage).toFixed(2)}`:''].filter(Boolean).join(' · ');
      const failing = (Array.isArray(o.gate_summaries)?o.gate_summaries:[]).filter(g => g && g.status === 'fail');
      body = `<div class="gate-chips">${chips}</div>${metrics?`<p>${metrics}</p>`:''}${failing.map(g => `<p class="gate-fail"><strong>${esc(g.gate)}</strong>: ${esc(g.summary||'')}${g.findings?.[0]?.message?` · ${esc(String(g.findings[0].message).slice(0,220))}`:''}</p>`).join('')}`;
    } else if (s?.span_kind === 'FAULT_LOCALIZATION' && Array.isArray(o.top)) {
      body = `<p>Most suspicious: ${o.top.slice(0,3).map(r => `<span class="mono">${esc(r.file)}:${esc(r.line)}</span> (${Number(r.ochiai).toFixed(2)})`).join(', ') || 'none ranked'}</p>`;
    } else if (phase.startsWith('SECURITY')) {
      const inj = Array.isArray(o.injection_findings) ? o.injection_findings.length : 0;
      const pol = Array.isArray(o.policy_findings) ? o.policy_findings : [];
      body = `<p>${inj} injection signal(s) neutralised${o.canary_leaked?' · system-prompt canary leaked':''}${pol.length?` · blocked: ${pol.map(f => esc(f.rule)).join(', ')}`:''}</p>`;
    }
    return {kind, body};
  }
  const caseName = id => cases[id]?.[0] || (String(id || '').startsWith('custom_') ? 'Custom Python repair' : String(id || 'Unknown case').replaceAll('_', ' '));
  function external(url, text, cls='button small') { return `<a class="${cls}" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} <span aria-hidden="true">↗</span></a>`; }
  async function request(path, {method='GET',body,timeout=30000,signal} = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const abort = () => controller.abort();
    if (signal) signal.addEventListener('abort', abort, {once:true});
    try {
      const response = await fetch(API + path, {method,signal:controller.signal,headers:{'Accept':'application/json',...(body!==undefined?{'Content-Type':'application/json'}:{})},...(body!==undefined?{body:JSON.stringify(body)}:{})});
      let data;
      try { data = await response.json(); } catch { throw new Error(`The server returned an unreadable response (HTTP ${response.status}). Please try again.`); }
      if (!response.ok) {
        if (response.status === 429) throw new Error('Too many requests. Wait ' + (response.headers.get('Retry-After') || '60') + ' seconds before retrying.');
        if (response.status >= 500) throw new Error('The service is temporarily unavailable. Your source repository is unchanged.');
        throw new Error(typeof data.detail === 'string' ? data.detail.slice(0,350) : `Request rejected (HTTP ${response.status}). Check your input.`);
      }
      return data;
    } catch (err) {
      if (err.name === 'AbortError') throw new Error(method === 'POST' ? 'The request timed out. The server may still be working. Refresh run history before starting another run.' : 'The request timed out. Check your connection and retry.');
      if (err instanceof TypeError) throw new Error('Could not reach the API. Check your connection and retry.');
      throw err;
    } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
  }
  function heading(eyebrow,title,desc,action='') { return `<div class="page-heading"><div><span class="eyebrow">${eyebrow}</span><h1>${title}</h1><p>${desc}</p></div>${action}</div>`; }
  function empty(title,desc,action='') { return `<div class="empty"><h2>${title}</h2><p>${desc}</p>${action}</div>`; }
  function loading(label) { return `<div class="loading" role="status"><span class="spinner" aria-hidden="true"></span>${label}</div>`; }
  function notice() {
    const el = $('notice'); el.hidden = !S.error || !S.data;
    el.innerHTML = S.error ? `${esc(S.error)} ${S.data?'Showing the last loaded records; these may be stale.':''} <button class="button small" data-action="refresh">Retry connection</button>` : '';
    $('connection').className = 'connection ' + (S.error?'offline':S.data?'online':'');
    $('connection').innerHTML = `<i></i>${S.loading?'Loading records':S.error?'API unavailable':S.data?'API connected':'Connecting'}`;
  }
  async function refresh() {
    if (S.loading) return;
    S.loading = true; $('refresh').disabled = true; notice();
    if (!S.data) render();
    try {
      const data = await request('/api/workspace');
      if (!data || !Array.isArray(data.runs) || !Array.isArray(data.benchmarks) || !Array.isArray(data.experiments)) throw new Error('The API response is incomplete. No records were displayed.');
      S.data = data; S.error = null; S.loadedAt = new Date();
    } catch (err) { S.error = err.message; }
    finally { S.loading = false; $('refresh').disabled = false; notice(); render(); }
  }
  const flowArt = `<svg viewBox="0 0 380 250" role="img" aria-label="Workflow: locate the bug, check downstream callers, verify the patch">
  <defs><pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#c2d1bb"/></pattern></defs><rect width="380" height="250" fill="url(#dots)"/>
  <path d="M84 122H150M225 122h70M188 94V55h93M188 150v45h93" fill="none" stroke="#a7baa3" stroke-width="1.4"/>
  <circle cx="84" cy="122" r="25" fill="#fff" stroke="#c6d5bf"/><text x="84" y="127" text-anchor="middle" fill="#53724c" font-size="17" font-family="monospace">{ }</text>
  <rect x="147" y="91" width="82" height="62" rx="14" fill="#214a36"/><path d="m176 120 9 9 17-21" fill="none" stroke="#d9f1d4" stroke-width="3"/>
  <rect x="277" y="36" width="85" height="37" rx="8" fill="#fff" stroke="#c6d5bf"/><text x="320" y="59" text-anchor="middle" font-size="10" fill="#53724c">Caller tests</text>
  <rect x="277" y="105" width="85" height="37" rx="8" fill="#fff" stroke="#c6d5bf"/><text x="320" y="128" text-anchor="middle" font-size="10" fill="#53724c">Repro test</text>
  <rect x="277" y="176" width="85" height="37" rx="8" fill="#fff" stroke="#c6d5bf"/><text x="320" y="199" text-anchor="middle" font-size="10" fill="#53724c">Patch evidence</text>
  <text x="84" y="166" text-anchor="middle" font-size="9" fill="#61795a">SOURCE</text><text x="188" y="178" text-anchor="middle" font-size="9" fill="#61795a">VERIFIX</text></svg>`;
  const factLabel = key => key.replace(/_/g,' ').replace(/\butc\b/,'(UTC)').replace(/\bpct\b/,'%').replace(/^./,c=>c.toUpperCase());
  function factValue(v) {
    if (v === null || v === undefined || v === '') return '—';
    if (Array.isArray(v)) return esc(v.join(', ') || '—');
    if (typeof v === 'object') return esc(Object.entries(v).map(([k,x])=>`${k}: ${x===true?'yes':x===false?'no':x}`).join(' · '));
    if (typeof v === 'number') return num(v,2);
    return esc(v);
  }
  async function loadProof() {
    if (S.proofLoading) return;
    S.proofLoading = true; S.proofError = null; if (S.route==='verify') render();
    try {
      const data = await request('/api/judge-proof', {timeout:30000});
      if (!data || !Array.isArray(data.items) || !data.summary) throw new Error('The verification response is incomplete. Please retry.');
      S.proof = data;
    } catch (err) { S.proofError = err.message; }
    finally { S.proofLoading = false; if (S.route==='verify') render(); }
  }
  function verify() {
    const action = `<button class="button" data-action="proof" ${S.proofLoading?'disabled':''}>${S.proofLoading?'Checking…':'Re-run checks'}</button>`;
    const head = heading('FOR JUDGES','Verify every claim in two minutes.','Each card answers one item of the official neatHack evidence checklist. <strong>LIVE</strong> items are checked against GitHub, neatlogs and this deployment when you open the page. <strong>RECORDED</strong> items come from versioned files in the repository.', action);
    if (!S.proof) return head + (S.proofLoading ? loading('Running live checks against GitHub and neatlogs…') : empty('Verification could not run.', esc(S.proofError || 'No result yet.'), '<button class="button primary" data-action="proof">Run the checks</button>'));
    const p = S.proof, sm = p.summary;
    const verdictTag = v => `<span class="tag ${v==='verified'?'success':v==='attention'?'warn':'fail'}">${v==='verified'?'✓ Verified':v==='attention'?'Not met':'Source unavailable'}</span>`;
    const cards = p.items.map(item => `<article class="panel proof-card" aria-labelledby="proof-${esc(item.id)}"><div class="badge-row">${verdictTag(item.verdict)}<span class="tag method-${esc(item.method.toLowerCase())}" title="${esc(p.method_legend?.[item.method] || '')}">${esc(item.method)}</span></div><h2 id="proof-${esc(item.id)}">${esc(item.criterion)}</h2><p class="proof-claim">${esc(item.claim)}</p><p>${esc(item.detail)}</p>${Object.keys(item.facts||{}).length?`<dl class="proof-facts">${Object.entries(item.facts).map(([k,v])=>`<div><dt>${esc(factLabel(k))}</dt><dd class="${/(_id|_run|run_id|trace|commit)/.test(k)?'mono':''}">${factValue(v)}</dd></div>`).join('')}</dl>`:''}<div class="button-row proof-links">${(item.links||[]).map(l => { const u=String(l.url||''); if (u.startsWith('#run/')) return `<button class="button small" data-inspect="${esc(u.slice(5))}">${esc(l.label)}</button>`; if (/^#[a-z]+$/.test(u) && Object.hasOwn(titles,u.slice(1))) return `<a class="button small" href="${esc(u)}">${esc(l.label)}</a>`; return /^https:\/\//.test(u) ? external(u,l.label) : ''; }).join('')}</div></article>`).join('');
    return head + `<div class="proof-summary" role="status"><div><strong>${sm.verified}</strong><span>verified</span></div><div><strong>${sm.attention}</strong><span>not met</span></div><div><strong>${sm.unavailable}</strong><span>source unavailable</span></div><p>Checked ${esc(new Date(p.generated_at).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'medium'}))} · ${num(p.elapsed_ms,0)} ms${p.cache_age_s?` · cached ${num(p.cache_age_s,0)} s ago`:''}. Nothing on this page is hard-coded as a pass: an unreachable source is shown as unavailable.</p></div>${S.proofError?`<div class="callout warn">${esc(S.proofError)} Showing the previous result.</div>`:''}<div class="proof-grid">${cards}</div>`;
  }
  function controlledSection() {
    const ce = S.data.controlled_experiment, head = '<div class="section-heading"><div><h2>Measured in a controlled experiment.</h2><p>Same model, prompt and attempt limit in every arm. Only the context changes. An independent judge runs each case\'s full test suite.</p></div><span class="tag">Measured, not projected</span></div>';
    if (!ce) return head + `<p class="provenance">The controlled experiment file is not included in this deployment, so no comparison is shown.</p>`;
    const g = ce.arms.graph_guarded, b = ce.arms.baseline_naive, t = ce.arms.target_only, vb = ce.comparisons.graph_guarded_vs_baseline_naive, vt = ce.comparisons.graph_guarded_vs_target_only, fi = ce.fault_injection?.arms;
    const fewer = r => num((1 - r) * 100, 0), ci = vb.token_ratio_ci95_cases;
    const caught = fi?.graph_guarded ? `${num(fi.graph_guarded.judge_passed)}/${num(fi.graph_guarded.runs)}` : '—';
    return head + `<div class="metrics"><article class="metric"><div class="label">Tokens vs. reading the whole repo <span aria-hidden="true">↘</span></div><div class="value">${fewer(vb.token_ratio_geo_mean)}% fewer</div><div class="sub"><span class="delta">95% CI ${fewer(ci[1])}–${fewer(ci[0])}%</span>${num(g.mean_total_tokens)} vs. ${num(b.mean_total_tokens)} tokens per fix · ${num(vb.pairs)} paired runs</div></article><article class="metric"><div class="label">Fixes that passed the independent judge <span aria-hidden="true">✓</span></div><div class="value">${num(g.judge_passed)}/${num(g.runs)}</div><div class="sub"><span class="delta">No loss of fixes</span>whole repo ${num(b.judge_passed)}/${num(b.runs)} · target file only ${num(t.judge_passed)}/${num(t.runs)}</div></article><article class="metric"><div class="label">Planted caller-breaking patch, recovered <span aria-hidden="true">⟲</span></div><div class="value">${caught}</div><div class="sub"><span class="delta">Rolled back, then fixed</span>${fi?.target_only ? `caller-blind agent shipped it ${num(fi.target_only.shipped_regressions)}/${num(fi.target_only.runs)}` : 'fault-injection file not included'}</div></article></div>
    <p class="provenance">${num(ce.records)} runs · ${num(vb.cases)} benchmark bugs × ${num(ce.design.repeats)} repeats · ${esc(isoDate(ce.last_recorded_at))}. Graph context costs ${num((vt.token_ratio_geo_mean - 1) * 100, 0)}% more tokens than the target file alone, and buys the caller check. Fault injection uses one scripted patch on one case. The earlier single comparison (31,093 → 946 tokens) used a handicapped baseline and is no longer a headline. ${external(SOURCE + '/blob/main/docs/EVALUATION.md', 'Method and data', 'button ghost')}</p>`;
  }
  function overview() {
    const run = S.data.runs.find(r => r.status === 'VERIFIED_COMPLETE' && cases[r.case_id]) || S.data.runs.find(r => r.status === 'VERIFIED_COMPLETE');
    return `<a class="judge-banner" href="#verify"><span><strong>Judging VeriFix?</strong> Every submission claim, checked live against GitHub, neatlogs and this deployment.</span><span class="judge-cta">Verify in 2 minutes →</span></a>` + heading('VERIFIED CODE REPAIR','A safer path from bug to fix.','Repair the issue. Check its callers. Keep the evidence.',external(SOURCE+'/blob/main/verifix_neathack_2026_demo.mp4','Watch demo')) +
    `<section class="hero" aria-labelledby="hero-title"><div class="hero-copy"><span class="eyebrow">SMALL PATCHES. A WIDER VIEW.</span><h2 id="hero-title">Fix the bug.<br>Protect what depends on it.</h2><p>VeriFix maps downstream callers before changing code, then checks the patch against both the bug and the contracts around it.</p><div class="button-row"><a href="#benchmarks" class="button primary">Run a benchmark <span aria-hidden="true">→</span></a><a href="#runs" class="button ghost">Explore run evidence ↗</a></div></div><div class="hero-art">${flowArt}<span class="hero-caption">THE VERIFICATION WORKFLOW</span></div></section>
    ${controlledSection()}
    <div class="two-col"><section class="panel"><div class="panel-heading"><h2>Inside a verified run</h2><span class="tag">Recorded execution</span></div>${run?`<div class="run-card"><span class="run-mark">${icon('check')}</span><div><div class="run-title">${esc(caseName(run.case_id))}</div><p class="mono">${esc(run.target_symbol)}</p><p>${time(run.created_at)}</p></div></div><dl class="run-facts"><div><dt>Attempts</dt><dd>${num(run.current_attempt)}</dd></div><div><dt>Total tokens</dt><dd>${num(run.total_tokens)}</dd></div><div><dt>Run latency</dt><dd>${sec(run.total_latency_ms)}</dd></div></dl><div class="panel-end">${status(run.status)}<button class="button small" data-inspect="${esc(run.run_id)}">Inspect patch <span aria-hidden="true">↗</span></button></div>`:empty('No verified runs yet','Run a benchmark to create a record.')}</section>
    <section class="panel"><div class="panel-heading"><h2>Verification, in three steps</h2><span class="tag">Start here</span></div><ol class="steps"><li><div><strong>Understand the impact</strong><p>Locate the bug and map the functions that depend on it.</p></div></li><li><div><strong>Repair without breaking callers</strong><p>Test a targeted patch. Roll back a failing candidate.</p></div></li><li><div><strong>Leave a reviewable trail</strong><p>Inspect the diff, execution steps and verification certificate.</p></div></li></ol></section></div>
    <div class="partner-strip"><span>CONNECTED WORKFLOW</span><div><strong>neatlogs</strong><small>Traces &amp; diagnostics</small></div><div><strong>Entire</strong><small>Graph, memory &amp; provenance</small></div><div><strong>cfo.ai model</strong><small>Financial planning · projections</small></div><div><strong>AWS Lambda</strong><small>Hosting &amp; patch attestation</small></div></div>`;
  }
  function rows() {
    const filter = S.filter.toLowerCase();
    const filtered = S.data.runs.filter(r => `${r.run_id} ${r.case_id} ${r.target_symbol}`.toLowerCase().includes(filter) && (S.status==='all' || (S.status==='verified'?r.status==='VERIFIED_COMPLETE':r.status!=='VERIFIED_COMPLETE')));
    const shown = filtered.slice(0, S.page * 10);
    $('run-rows').innerHTML = shown.map(r => `<tr><td><button class="table-link" data-inspect="${esc(r.run_id)}">${esc(caseName(r.case_id))}</button><small>${esc(r.target_symbol)}</small></td><td>${status(r.status)}</td><td>${num(r.total_tokens)}</td><td>${sec(r.total_latency_ms)}</td><td>${money(r.accumulated_cost_usd)}</td><td>${time(r.created_at)}</td></tr>`).join('');
    $('runs-empty').hidden = filtered.length > 0; $('run-table').hidden = !filtered.length;
    $('run-count').textContent = `${shown.length} of ${filtered.length} matching records · up to 100 most recent records in this instance`;
    $('more-runs').hidden = shown.length >= filtered.length;
  }
  function runs() { return heading('EXECUTION RECORDS','Every repair has a trail.','Inspect a patch, its tests, and the decisions behind it.','<a class="button primary" href="#benchmarks">New benchmark →</a>') +
    `<div class="toolbar"><label class="field-label" for="run-search">Find a run</label><input id="run-search" type="search" maxlength="200" placeholder="Search case, symbol or run ID…" value="${esc(S.filter)}"><label class="field-label" for="run-status">Status</label><select id="run-status"><option value="all">All statuses</option><option value="verified" ${S.status==='verified'?'selected':''}>Verified</option><option value="other" ${S.status==='other'?'selected':''}>Other outcomes</option></select></div><div class="table-wrap" id="run-table" tabindex="0" role="region" aria-label="Scrollable run history"><table><thead><tr><th scope="col">Case / target</th><th scope="col">Outcome</th><th scope="col">Tokens</th><th scope="col">Latency</th><th scope="col">API cost</th><th scope="col">Recorded</th></tr></thead><tbody id="run-rows"></tbody></table></div><div id="runs-empty" hidden>${empty('No matching runs','Try another search or change the status filter.','<button class="button" data-action="clear-filters">Clear filters</button>')}</div><div class="panel-end"><p id="run-count" class="provenance" role="status"></p><button class="button small" id="more-runs" data-action="more">Show 10 more</button></div><p class="provenance">Lambda records are instance-local and ephemeral. The versioned ledger contains release-time evidence, not a globally durable production run history.</p>`;
  }
  function benchmarks() {
    return heading('LIVE EXECUTION','Start with a known bug.','Choose a small Python benchmark. VeriFix repairs it in a separate worktree.') +
    `<div class="two-col" style="margin-top:0"><section class="panel"><h2>01 &nbsp; Choose a benchmark</h2><div class="case-grid">${S.data.benchmarks.map((c,i)=>`<button class="case-option" data-case="${esc(c.case_id)}" aria-pressed="${S.caseId===c.case_id}" ${S.running?'disabled':''}><span class="radio-dot" aria-hidden="true"></span><small>CASE ${String(i+1).padStart(2,'0')} / PYTHON</small><strong>${esc(caseName(c.case_id))}</strong><p>${esc(cases[c.case_id]?.[1]||c.title)}</p></button>`).join('')}</div><h2>02 &nbsp; Run with caller protection</h2><p class="muted" style="font-size:12px;margin:12px 0">Focused graph context, a targeted patch, and downstream verification. No source repository changes.</p><details><summary>Advanced · controlled failure tests</summary><p>These options deliberately inject faults into this benchmark. They are not ordinary production failures.</p><label class="check-row"><input id="trap" type="checkbox" ${S.running?'disabled':''}>Inject a caller-contract regression</label><label class="check-row"><input id="interrupt" type="checkbox" ${S.running?'disabled':''}>Pause after reproduction (inspect checkpoint)</label></details><div class="callout">Live model usage is billable. You will confirm before execution. Requests are never automatically retried.</div><button class="button primary" data-action="start-run" ${S.running||!S.data.benchmarks.length?'disabled':''}>${S.running?'<span class="spinner" aria-hidden="true"></span>Benchmark running…':'Review & run benchmark →'}</button><div class="status-output" id="run-result" role="status">${runResult()}</div></section>
    <aside class="panel"><span class="eyebrow">WHAT TO EXPECT</span><h2>A real run, not a replay.</h2><p class="muted" style="font-size:12px;margin:14px 0 24px">The model generates a new candidate. Results and latency can differ from the recorded experiments.</p><ol class="steps"><li><div><strong>Reproduce</strong><p>Confirm the failing behavior in the selected repository.</p></div></li><li><div><strong>Repair &amp; verify</strong><p>Generate a patch and run reproduction and caller checks.</p></div></li><li><div><strong>Inspect the outcome</strong><p>A verified result, a checkpoint, or a failure with evidence.</p></div></li></ol><details><summary>Scope &amp; safety limits</summary><p>Only four catalogued repositories are offered here. Arbitrary repository paths and uploaded Python execution are operator-only because a temporary folder is not a security sandbox.</p><p>Configured limits: 3 attempts, 20 tools, $0.25 model budget. Public execution is serialized within each server instance and rate-limited. These are not account-wide spending controls.</p></details></aside></div>`;
  }
  function runResult() {
    if (S.running) return 'Executing against the live API. You can explore other screens while waiting. No simulated progress is shown.';
    if (S.runError) return `<strong>Run could not be confirmed</strong><p>${esc(S.runError)}</p><a class="button ghost" href="#runs">Check run history →</a>`;
    if (!S.result) return '';
    return `${status(S.result.status)}<p class="mono">${esc(S.result.run_id)}</p><button class="button small" data-inspect="${esc(S.result.run_id)}">Inspect run evidence ↗</button>`;
  }
  function evidence() {
    return heading('CHECKABLE, NOT JUST CLAIMED','Follow the evidence.','Runtime measurements, development provenance and projections — kept separate.') +
      `<div class="segmented" role="group" aria-label="Evidence category">${[['neatlogs','neatlogs'],['entire','Entire'],['finance','Financial model'],['oss','Open source']].map(([id,label])=>`<button data-evidence="${id}" aria-pressed="${S.evidence===id}">${label}</button>`).join('')}</div><div id="evidence-content">${evidenceContent()}</div>`;
  }
  function evidenceContent() {
    if (S.evidence==='neatlogs') {
      const exp = S.data.experiments[0];
      return `<p class="evidence-intro">Trace data helps explain the repair, not just its final status. The screenshot and experiment below are recorded artifacts, not a live global analytics feed.</p><div class="evidence-grid"><section class="panel"><span class="eyebrow">DIAGNOSTICS</span><h2>Neatlogs analytics snapshot</h2><p>Historical capture supplied for the v4 release. Global trace averages and a single benchmark measure different workloads; they should not be compared as equivalent samples.</p>${external(API+'/screenshots/09_neatlogs_analytics_410_traces_v3_v4.png','Open full-size screenshot')}<img class="evidence-image" src="${API}/screenshots/09_neatlogs_analytics_410_traces_v3_v4.png" alt="Recorded Neatlogs analytics: 410 traces, 5.0 second average duration, 5.1 percent error rate" loading="lazy"></section><section class="panel"><span class="eyebrow">BENCHMARK EVIDENCE</span><h2>Historical before / after runs</h2><p>The first recorded comparison. Its baseline was handicapped: a forced bad first patch, an extra model call and unrelated docs in the prompt. The controlled experiment on the overview replaces it as the headline.</p>${exp?`<p class="mono">${esc(exp.experiment_id)}</p><div class="button-row"><button class="button small" data-inspect="${esc(exp.run_a_id)}">Inspect baseline</button><button class="button small" data-inspect="${esc(exp.run_b_id)}">Inspect optimized run</button></div><details><summary>Raw experiment record</summary><pre tabindex="0">${pretty(exp)}</pre></details>`:empty('No experiment recorded','Run evidence will appear when available.')}<details><summary>When remote trace readback stalls</summary><p>VeriFix can expose its own locally recorded steps. This does not finalize a remote Neatlogs trace or recover another team's missing spans.</p>${external(API+'/api/neatlogs-trace-readback','Local trace readback')}</details></section></div>`;
    }
    if (S.evidence==='entire') {
      const entire=S.data.entire || {}, commits=entire.recent_commits || [];
      return `<p class="evidence-intro">Entire Graph supports code context and caller analysis. Brain stores development memory. Checkpoints record development provenance; they are not a production runtime dependency.</p><div class="evidence-grid"><section class="panel"><span class="eyebrow">DEVELOPMENT PROVENANCE</span><h2>Checkpoint-linked commits</h2><p>Release-time Git metadata. Follow a commit to inspect its associated record. Token totals in imported transcripts are not independently audited usage.</p><ul class="timeline">${commits.slice(0,5).map(c=>`<li><h3>${esc(c.subject)}</h3><p>${esc(c.hash)} · ${esc(c.date)}</p>${/^[a-f0-9]{40}$/.test(c.full_hash||'')?external('https://entire.io/gh/shivanshjain456/neatHack/commit/'+c.full_hash,'Inspect provenance','button ghost'):''}</li>`).join('')||'<li>No commit metadata available.</li>'}</ul></section><section class="panel"><span class="eyebrow">GRAPH &amp; MEMORY</span><h2>Inspect the caller context</h2><p>Ask the API for the graph around a Python symbol, or examine the existing intelligence modules. These operations load only when requested.</p><form id="graph-form"><div class="field"><label for="symbol">Python symbol</label><input id="symbol" name="symbol" required maxlength="128" pattern="[A-Za-z_][A-Za-z0-9_.]*" value="calculate_tiered_fee"></div><button class="button primary" type="submit">Inspect graph →</button></form><div class="button-row" style="margin-top:14px"><button class="button small" data-action="intelligence">Inspect intelligence modules</button></div><div id="graph-output" class="status-output" role="status"></div><details><summary>Snapshot metadata</summary><pre tabindex="0">${pretty({refs:entire.entire_refs,graph_stats:entire.entire_graph_stats,brain:entire.entire_brain})}</pre></details></section></div>`;
    }
    if (S.evidence==='finance') {
      const model=S.data.cfo_model, plan=S.data.plan_projection, whole=v=>finite(v)?(Number(v)<0?'−$':'$')+num(Math.abs(Math.round(v))):'—';
      const scenarios=Object.entries(model?.scenarios || {}).map(([name,q])=>[name,Array.isArray(q)?q.at(-1):null]).filter(([,q])=>q);
      const planPanel=plan?.milestones?.length?`<section class="panel"><span class="eyebrow">24-MONTH PLAN · PLAN.XLSX</span><h2>Break-even in month ${esc(plan.first_positive_ebitda_month)}</h2><p>Recalculated from the workbook formulas. The lowest projected cash balance is ${whole(plan.lowest_cash?.ending_cash)} in month ${esc(plan.lowest_cash?.month)}, starting from $150,000.</p><div class="table-wrap"><table><caption class="sr-only">Plan milestones</caption><thead><tr><th scope="col">Month</th><th scope="col">Customers</th><th scope="col">Monthly revenue</th><th scope="col">ARR</th><th scope="col">EBITDA</th><th scope="col">Ending cash</th></tr></thead><tbody>${plan.milestones.map(m=>`<tr><td>M${esc(m.month)}</td><td>${num(m.total_customers)}</td><td>${whole(m.total_monthly_revenue)}</td><td>${whole(m.arr)}</td><td>${whole(m.ebitda)}</td><td>${whole(m.ending_cash)}</td></tr>`).join('')}</tbody></table></div></section>`:`<section class="panel"><span class="eyebrow">24-MONTH PLAN · PLAN.XLSX</span><h2>Plan figures unavailable</h2><p>This deployment could not read the recalculated workbook snapshot. The workbook itself is still linked below.</p></section>`;
      const scenarioPanel=scenarios.length?`<section class="panel"><span class="eyebrow">STRESS TEST · SEPARATE SHEET</span><h2>Stress test: retry-heavy model costs</h2><p>The workbook's scenario sheet uses its own static assumptions for Q4 (Jul–Sep 2027). The downside case assumes the cost per run of the historical handicapped baseline, an upper-bound stress input, not the controlled measurement. In that case model costs exceed revenue.</p><div class="table-wrap"><table><caption class="sr-only">Scenario comparison</caption><thead><tr><th scope="col">Scenario</th><th scope="col">Annualised revenue</th><th scope="col">Gross margin</th><th scope="col">Ending cash</th></tr></thead><tbody>${scenarios.map(([name,q])=>`<tr><td>${esc(name.replace(/\s*\(.*\)$/,''))}<small>${esc((name.match(/\((.*)\)$/)||[])[1]||'')}</small></td><td>${whole(q.arr_usd)}</td><td>${num(q.gross_margin_pct,1)}%</td><td>${whole(q.ending_cash_usd)}</td></tr>`).join('')}</tbody></table></div><p>Modeled cost per verified run with graph context: ${money(model?.telemetry_provenance?.run_b_graph_guarded?.modeled_enterprise_cost_per_run_usd)}.</p></section>`:'';
      return `<div class="callout warn">Planning projections — not realized revenue, profit, customer adoption, or a runtime dependency.</div><div class="evidence-grid stack">${planPanel}${scenarioPanel}</div><div class="button-row spaced">${external(RAW+'plan.xlsx','Download workbook')}${external(SOURCE+'/blob/main/BUSINESS_PLAN.md','Read assumptions')}</div>`;
    }
    return `<p class="evidence-intro">The open-source investigation is documented separately from the fixed benchmark suite. An upstream pull request is a contribution, not a claim that the change has been merged.</p><div class="evidence-grid"><section class="panel"><span class="eyebrow">NEATLOGS SDK</span><h2>Concurrent exporter capacity</h2><p>Investigated dropped telemetry under concurrent masking work. The proposed change uses deadline-bounded semaphore acquisition rather than immediately dropping work when capacity is busy.</p><div class="button-row">${external('https://github.com/neatlogs/neatlogs/issues/199','Read issue #199')}${external('https://github.com/neatlogs/neatlogs/pull/203','Review PR #203')}</div>${external(SOURCE+'/blob/main/REAL_OSS_BUG_REPORT_NEATLOGS.md','Read reproduction report','button ghost')}</section><section class="panel"><span class="eyebrow">LOCAL REPRODUCTION</span><h2>Run the concurrency comparison</h2><p>Executes a small semaphore-based reproduction of the reported behavior. This is not a rerun of the upstream repository's entire test suite.</p><button class="button" data-action="oss">Run bounded comparison →</button><div id="oss-output" class="status-output" role="status"></div></section></div>`;
  }
  function system() {
    return heading('OPERATIONS & QUALITY','Know the limits. Check the system.','A clear boundary between a working research release and production assurances.') +
    `<div class="evidence-grid"><section class="panel"><span class="eyebrow">LIVE DIAGNOSTICS</span><h2>Check the connected environment</h2><p>Runs the existing partner-integration self-checks against this deployment. Read each result: a green check is not a security certification or a service-level guarantee.</p><button class="button primary" data-action="selftest" ${S.diagnosticBusy?'disabled':''}>${S.diagnosticBusy?'Checking environment…':'Run environment checks →'}</button><div class="status-output" role="status">${S.diagnostic?`<pre tabindex="0">${pretty(S.diagnostic)}</pre>`:''}</div><details><summary>Connection details</summary><p>API: <span class="mono">${esc(API || location.origin)}</span></p><p>Last workspace fetch: ${S.loadedAt?esc(S.loadedAt.toLocaleString()):'Not loaded'}. A connected API does not imply that every external provider is available.</p></details></section><section class="panel"><span class="eyebrow">RELEASE EVIDENCE</span><h2>Tests you can inspect</h2><p>The release report records commands, browser assertions, screenshots and limitations. Simulated fault fixtures are test-only and are never presented as actual service responses.</p><div class="button-row">${external(SOURCE+'/blob/main/QUALITY_REPORT.md','Read quality report')}${external(SOURCE+'/tree/main/tests','Inspect test code')}</div><details open><summary>Deployment limitations</summary><p>SQLite and rate limits are local to a Lambda execution environment. Warm-instance run records can disappear at recycle. Durable, shared storage and account-wide quotas are required before production multi-user operation.</p><p>Public arbitrary-code execution is blocked. Operator-only endpoints require a server-side bearer token. Destructive load, penetration and chaos testing against shared infrastructure is not performed.</p></details></section></div><section class="panel" style="margin-top:20px"><span class="eyebrow">ADVANCED OPERATOR WORKFLOWS</span><h2>Custom repositories &amp; code</h2><p class="muted" style="font-size:12px;margin-top:12px">Custom targets, code playgrounds and automatic discovery remain available to trusted operators through the authenticated API or local CLI. They are deliberately not an anonymous web form: subprocess execution is not a hardened multi-tenant sandbox.</p>${external(SOURCE+'/blob/main/README.md','Read operator documentation','button ghost')}</section>`;
  }
  function render() {
    $('breadcrumb').textContent = titles[S.route];
    document.title = `${titles[S.route]} · VeriFix`;
    document.querySelectorAll('[data-route]').forEach(a => { if(a.dataset.route === S.route) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
    if (S.route === 'verify') { $('screen').innerHTML = verify(); return; }
    if (!S.data) { $('screen').innerHTML = S.loading?loading('Loading recorded evidence…'):empty('The workspace could not connect.',esc(S.error || 'No data is available.'),'<button class="button primary" data-action="refresh">Retry connection</button>'); return; }
    $('screen').innerHTML = ({overview,runs,benchmarks,evidence,system})[S.route]();
    if (S.route==='runs') rows();
  }
  function route() {
    const next=location.hash.slice(1) || 'overview';
    if (!Object.hasOwn(titles,next)) { history.replaceState(null,'','#overview'); S.route='overview'; } else S.route=next;
    if (S.route === 'verify' && !S.proof && !S.proofLoading) loadProof();
    render(); $('main').focus({preventScroll:true}); window.scrollTo({top:0,behavior:'instant'});
  }
  async function inspect(id) {
    const version=++inspectionVersion;
    $('dialog-title').textContent='Run evidence'; $('run-detail').innerHTML=loading('Loading run evidence…');
    if (!$('run-dialog').open) $('run-dialog').showModal();
    try {
      const r=await request('/api/runs/'+encodeURIComponent(id));
      if(version!==inspectionVersion) return;
      $('dialog-title').textContent=caseName(r.case_id);
      const cert=r.verification_certificate || {}, att=cert.aws_lambda_attestation || {};
      const callers=r.blast_radius?.direct_callers || [];
      $('run-detail').innerHTML=`<div class="badge-row">${status(r.status)}<span class="tag">${esc(r.mode)}</span></div><p class="inspector-summary mono">${esc(r.run_id)} · ${esc(r.target_symbol)}</p><p class="inspector-summary">${time(r.created_at)}${cert.neatlogs_trace_id?` · neatlogs trace <span class="mono">${esc(cert.neatlogs_trace_id)}</span>`:''}</p><div class="data-grid"><div><small>Attempts</small><strong>${num(r.current_attempt)}</strong></div><div><small>Total tokens</small><strong>${num(r.total_tokens)}</strong></div><div><small>Recorded latency</small><strong>${sec(r.total_latency_ms)}</strong></div></div>${r.error_reason?`<div class="callout warn">${esc(r.error_reason)}</div>`:''}<div class="button-row">${external(API+'/api/runs/'+encodeURIComponent(id)+'/pr-evidence','Open JSON evidence')}${external(API+'/runs/'+encodeURIComponent(id)+'/share','Open shareable report')}${r.status==='INTERRUPTED_CHECKPOINTED'?`<button class="button" data-resume="${esc(id)}" ${S.running?'disabled':''}>Resume checkpoint</button>`:''}</div><div class="section-heading"><h2>Patch diff</h2><span class="tag">${num(r.rollbacks_executed)} rollbacks</span></div><pre class="diff" tabindex="0" aria-label="Scrollable patch diff">${r.final_diff?esc(r.final_diff):'No final patch was recorded for this outcome.'}</pre><h2>Execution trail</h2><ol class="trace-list">${(r.steps||[]).map(s=>{const d=stepDetail(s);return `<li><span class="trace-num">${num(s.seq_num)}</span><div><strong>${d.kind}${esc(s.title)}</strong><p>${esc(s.phase)} · ${sec(s.latency_ms)} · ${num(s.tokens_used)} tokens</p>${d.body}</div>${status(s.status)}</li>`;}).join('')||'<li>No steps recorded.</li>'}</ol><details><summary>Downstream callers (${callers.length})</summary><pre tabindex="0">${pretty(callers)}</pre></details><details><summary>Verification certificate${att.attested?' · attestation recorded':''}</summary><p>Attestation records the submitted patch digest and reported checks. It is not an independent security audit.</p><pre tabindex="0">${pretty(cert)}</pre></details>`;
    } catch(err) { if(version===inspectionVersion) $('run-detail').innerHTML=empty('Run evidence unavailable',esc(err.message),`<button class="button" data-inspect="${esc(id)}">Retry this run</button>`); }
  }
  let pendingRun=null;
  async function execute(payload,path='/api/run') {
    if(S.running) return;
    S.running=true; S.result=null; S.runError=null; render();
    try {
      const result=await request(path,{method:'POST',body:payload,timeout:180000});
      if(!result?.run_id || !result?.status) throw new Error('The run response has no ID or outcome. Check run history before retrying.');
      S.result=result;
      await refresh();
    } catch(err) { S.runError=err.message; }
    finally { S.running=false; render(); }
  }
  async function panelRequest(button,outputId,path,body) {
    const output=$(outputId); if(!output) return;
    button.disabled=true; output.innerHTML=loading('Requesting evidence…');
    try { const data=await request(path,{method:'POST',body,timeout:60000}); output.innerHTML=`<pre tabindex="0">${pretty(data)}</pre>`; }
    catch(err) { output.textContent=err.message; }
    finally { button.disabled=false; }
  }
  document.addEventListener('click', async event => {
    const inspectButton=event.target.closest('[data-inspect]'); if(inspectButton) { inspect(inspectButton.dataset.inspect); return; }
    const caseButton=event.target.closest('[data-case]'); if(caseButton && !S.running) { S.caseId=caseButton.dataset.case; render(); document.querySelector(`[data-case="${CSS.escape(S.caseId)}"]`)?.focus(); return; }
    const evidenceButton=event.target.closest('[data-evidence]'); if(evidenceButton) { S.evidence=evidenceButton.dataset.evidence; render(); document.querySelector(`[data-evidence="${S.evidence}"]`)?.focus(); return; }
    const resume=event.target.closest('[data-resume]'); if(resume && !S.running) { pendingRun={path:'/api/resume',body:{run_id:resume.dataset.resume}}; $('confirm-dialog').showModal(); return; }
    const button=event.target.closest('[data-action]'); if(!button || button.disabled) return;
    switch(button.dataset.action) {
      case 'refresh': refresh(); break;
      case 'proof': loadProof(); break;
      case 'clear-filters': S.filter=''; S.status='all'; S.page=1; render(); $('run-search').focus(); break;
      case 'more': S.page++; rows(); break;
      case 'start-run': if(!S.running) { pendingRun={path:'/api/run',body:{case_id:S.caseId,mode:'graph_guarded',inject_caller_trap:!!$('trap')?.checked,interrupt_after_repro:!!$('interrupt')?.checked}}; $('confirm-dialog').showModal(); } break;
      case 'oss': panelRequest(button,'oss-output','/api/oss-bug-benchmark'); break;
      case 'intelligence': panelRequest(button,'graph-output','/api/entire-intelligence',{symbol:$('symbol').value,case_id:S.caseId}); break;
      case 'selftest': S.diagnosticBusy=true; render(); try {S.diagnostic=await request('/api/selftest',{timeout:60000});} catch(err) {S.diagnostic={error:err.message};} finally {S.diagnosticBusy=false;render();} break;
    }
  });
  document.addEventListener('submit',event=>{if(event.target.id==='graph-form'){event.preventDefault();panelRequest(event.target.querySelector('button'),'graph-output','/api/graph-inspect',{symbol:$('symbol').value.trim()});}});
  document.addEventListener('input',event=>{if(event.target.id==='run-search'){S.filter=event.target.value;S.page=1;rows();}});
  document.addEventListener('change',event=>{if(event.target.id==='run-status'){S.status=event.target.value;S.page=1;rows();}});
  $('refresh').addEventListener('click',refresh);
  $('close-dialog').addEventListener('click',()=>$('run-dialog').close());
  $('run-dialog').addEventListener('close',()=>{inspectionVersion++;});
  ['cancel-x','cancel-run'].forEach(id=>$(id).addEventListener('click',()=>$('confirm-dialog').close()));
  $('confirm-run').addEventListener('click',()=>{if(!pendingRun || S.running)return;const run=pendingRun;pendingRun=null;$('confirm-dialog').close();$('run-dialog').close();execute(run.body,run.path);});
  document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex="0"]')].filter(el => !el.disabled && el.getClientRects().length && (!el.closest('details:not([open])') || el.tagName === 'SUMMARY'));
    if (!controls.length) { event.preventDefault(); return; }
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }));
  window.addEventListener('hashchange',route);
  window.addEventListener('offline',()=>{S.error='Your browser is offline.';notice();});
  window.addEventListener('beforeunload',event=>{if(S.running){event.preventDefault();event.returnValue='';}});
  icons(); route(); refresh();
})();
