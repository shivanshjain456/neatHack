# cfo.ai evidence

1. **The model is recomputed from measured tokens, and CI fails on drift.**
   `scripts/compute_plan_values.py` rebuilds every plan figure from versioned
   telemetry; `plan.xlsx` and `benchmarks/plan_xlsx_computed.json` must match or a
   test fails. Sources: `BUSINESS_PLAN.md`, `plan.xlsx`,
   `benchmarks/cfo_ai_verified_model.json`.
2. **Cost drivers are measured, not assumed.** `benchmarks/cost_caps.json` records
   129 priced runs: mean $0.005176, p50 $0.000311, p90 $0.012839, max $0.145479, per
   mode, against the configured $0.25 public cap — p90 sits 94.9% under the cap.
3. **Every run ends with a receipt.** One file per recorded run in
   `benchmarks/receipts/`, carrying priced cost, cap, cap-used share and proof
   status, with a `sha256` over every other field; `index.json` hashes the ledger.
   The dashboard run inspector shows the same receipt per run (priced / cap / cap
   used / proof).
4. **Headline outputs are projections and labelled so.** Month-24 ARR $2,264,709 and
   first positive EBITDA at month 11 are projections from measured per-run cost;
   every surface that shows them says "projection" (`docs/comparison.md`,
   dashboard finance panel, video scene 10).
5. **Stress cases are disclosed.** The downside scenario sheet uses the retired
   handicapped baseline's cost as an upper-bound stress input and says so; in that
   scenario model costs exceed revenue (`BUSINESS_PLAN.md`).
