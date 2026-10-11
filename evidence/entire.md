# Entire evidence

1. **The build history carries Entire checkpoints.** 24 commits in the public history
   carry an `Entire-Checkpoint` trailer, and origin publishes 24 matching
   `refs/entire/*` refs. Verify from any clone:

   ```bash
   git log --no-merges --format='%(trailers:key=Entire-Checkpoint,valueonly=true)' | grep -c .
   git ls-remote origin 'refs/entire/*' | wc -l
   ```

2. **The submission commit is checkpoint-linked.** Commit
   [`10c7406723f285cc778b729863365713735e9191`](https://entire.io/gh/shivanshjain456/neatHack/commit/10c7406723f285cc778b729863365713735e9191)
   pairs with checkpoint `01M4KFYKQXFHME1HRZJVXJ7YT8`.
3. **Entire Graph is the runtime caller source, not a nice-to-have.**
   `src/verifix/graph_engine.py` builds the downstream-caller list the guardrail
   tests before accepting a patch; the 62%-fewer-tokens result is the cost of that
   context versus reading the whole repository (`docs/EVALUATION.md`). If the graph
   is empty, a run reports `REPRO_PASSED_CALLERS_UNCHECKED` rather than claiming full
   caller verification — the receipt states which checks ran.
4. **Entire Brain/development memory is used and disclosed.** Intelligence modules
   (`src/verifix/entire_intelligence.py`) record development memory; the dashboard
   Evidence library shows graph stats and brain snapshot metadata, with the caveat
   that checkpoints are development provenance, not a production runtime dependency.
5. **Telemetry snapshot is versioned.** `benchmarks/entire_telemetry_snapshot.json`
   records the refs, graph stats and brain state at release time; token totals in
   imported transcripts are labelled as not independently audited usage.
