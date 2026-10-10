# VeriFix (Team HyperX) — `cfo.ai` Business Plan & Telemetry-Grounded Unit Economics

> **Built for neatHack 2026 (`cfo.ai` + `neatlogs` + `Entire` Integration)**  
> **Workbook Artifact**: [`plan.xlsx`](./plan.xlsx) (100% deterministic Excel formulas across `Board_Overview`, `Assumptions`, `24M_Main_Model`, and `4Q_Scenario_Comparison`)  
> **JSON / MCP Model Artifact**: [`benchmarks/cfo_ai_verified_model.json`](./benchmarks/cfo_ai_verified_model.json)

---

## 1. Executive Thesis: Why Autonomous Patching Economics Break Without Code-Graph Context

Autonomous bug-fixing agents suffer from a fatal unit-economics trap: **unbounded repository exploration and retry loops**.
When a naive coding agent (`v1 baseline_naive`) attempts to fix a production defect, it reads entire files across the repository and frequently ships patches that pass the narrow reproduction test while breaking downstream callers—triggering expensive multi-turn retry loops.

**VeriFix** solves both the **reliability wall** and the **COGS wall** by coupling three systems into one closed loop:
1. **`Entire` (`Checkpoints` + `entire-graph` + `Entire Brain`)**: Replaces full-repo prompt stuffing with 1-hop semantic blast-radius localization (`search`, `impact`, `neighbors`) and persistent cross-session architectural memory (`recall`, `remember`).
2. **`neatlogs` (`AGENT`, `RETRIEVER`, `GUARDRAIL` Spans + 7 Active Detections)**: Measures exact token, latency, and retry overhead per step while enforcing a hard per-run budget guardrail (`3 tries, 20 tool calls, $0.25 max cost`).
3. **`cfo.ai` Deterministic Financial Engine**: Pipes live Neatlogs token/cost telemetry directly into our 24-month operating model (`plan.xlsx`) and interactive **Ari Board Overview** simulator.

---

## 2. Four-Generation Iterative Telemetry Optimization (`v1` Naive -> `v2` Graph-Guarded -> `v3` Coalesced Turbo -> `v4` Surgical Fast-Tier)

Every unit-cost assumption in `plan.xlsx` (`Assumptions!C13:C20`) is grounded in live experiments (`exp_0e3f5ca743`, `exp_bd53a0e4a4`, and `exp_24aa3f2776`) traced across **410+ traces** in Neatlogs (`Project ID: 00201e50-a8c9-42cf-84bf-116568a49cd5`), where our global error rate dropped from **`6.0%` (`350` traces) to `5.1%` (`410+` traces)** and global average tokens dropped from **`829.466` to `721.641` (`-13.0%`)**:

| Telemetry Driver (`case_01_ledger_rounding`) | `v1` Naive (`baseline_naive`) | `v2` Graph-Guarded (`exp_0e3f5ca743`) | `v3` Coalesced Turbo (`exp_bd53a0e4a4`) | **`v4` Surgical Fast-Tier (`exp_24aa3f2776`)** | **`v4` Improvement vs `v1`** |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Prompt Tokens / Run** | `26,743` (`12,216` in `v2` exp) | `4,269` | `1,533` | **`598`** *(avg `531` across 4 cases)* | **`-97.76%` (`44.7x` smaller)** |
| **Completion Tokens / Run** | `4,350` (`2,179` in `v2` exp) | `953` | `685` | **`348`** *(avg `282` across 4 cases)* | **`-92.00%`** |
| **Total Tokens / Run** | `31,093` (`14,395` in `v2` exp) | `5,222` | `2,218` | **`946`** *(avg `813` across 4 cases)* | **`-96.96%` (`32.9x` smaller)** |
| **End-to-End Run Latency** | `41,381.72 ms` | `11,914.84 ms` | `4,682.46 ms` | **`1,482.64 ms`** *(`1,407.22 ms` peak warm)* | **`-96.42%` (`27.9x` faster)** |
| **Direct API Cost / Run** | `$0.145479` | `$0.027057` | `$0.014874` | **`$0.000298`** *(avg `$0.000249` across 4 cases)* | **`-99.80%` (`488x` cheaper)** |
| **Modeled Enterprise Direct COGS / Run** | `$1.8626` (`$0.8896` in `v2` exp) | `$0.1794` | `$0.0946` | **`$0.0451`** | **`-97.58%` (`41.3x` lower COGS)** |
| **`run_pytest_target` Verification Latency** | `339ms P50 / 847ms P95` (`2` calls) | `339ms P50 / 847ms P95` | `36.8ms` (`1` combined `-S` pass) | **`21.4ms` (`-B -S` zero-pyc runner)** | **`-93.7% P50 / -97.5% P95`** |
| **`entire_graph_impact` / Context Retrieval** | N/A | `254ms P50 / 4,400ms P95` | `2.7ms` warm / `577ms` cold | **`0.4ms` warm (`_GRAPH_MEM_CACHE`)** | **`>99.9%` warm speedup** |

---

## 3. Pricing Architecture & Dodo Payments Merchant-of-Record Integration

VeriFix monetizes via a hybrid **SaaS Seat/Repo Subscription + Verified Remediation Overage** model billed globally through **Dodo Payments** (`3.9% + $0.40` Merchant-of-Record fee handling global VAT/GST and usage metering):

| Tier | Monthly Price | Included Verified Runs | Overage / Extra Verified Run | Target Customer Profile | Gross Margin (`v2` Flash) | Gross Margin (`v2` Enterprise Frontier) |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: |
| **Solo Pro** | **`$49 / mo`** | `100 runs/mo` | `$0.60 / run` | Independent engineers & solo founders | `99.1%` | `79.7%` *(vs `-21.7%` in `v1`!)* |
| **Team Guarded** | **`$249 / mo`** | `600 runs/mo` | `$0.45 / run` | 5–15 engineer product teams with CI gates | `98.9%` | `78.4%` |
| **Enterprise VPC** | **`$999 / mo`** | `3,000 runs/mo` | `$0.35 / run` | Regulated fintech/cloud orgs (`us-east-1` VPC) | `98.6%` | `75.8%` |

---

## 4. Revenue, Costs and Runway — 24-Month Main Model (`plan.xlsx → 24M_Main_Model`)

> **Projection, not realised results.** Every figure below is the workbook's own formula output, recalculated with
> [`scripts/compute_plan_values.py`](./scripts/compute_plan_values.py) and stored in
> [`benchmarks/plan_xlsx_computed.json`](./benchmarks/plan_xlsx_computed.json). `tests/test_web_release.py` fails if this
> document and the workbook disagree.

| Month | Paying customers | Verified runs / mo | Revenue / mo (subscription + usage) | ARR | COGS / mo | Gross margin | OpEx / mo | EBITDA / mo | Ending cash |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| M1 (launch) | 18 (14 Solo / 3 Team / 1 Enterprise) | 5,038 | $2,704 | $32,449 | $204 | 92.5% | $18,247 | $-15,747 | $134,253 |
| M6 | 94 (71 Solo / 19 Team / 4 Enterprise) | 24,742 | $13,542 | $162,505 | $1,014 | 92.5% | $19,456 | $-6,928 | $80,137 |
| M12 (year 1) | 291 (225 Solo / 59 Team / 7 Enterprise) | 63,920 | $36,161 | $433,928 | $2,685 | 92.6% | $28,653 | $4,822 | $55,909 |
| M24 (year 2) | 1,873 (1523 Solo / 337 Team / 13 Enterprise) | 318,496 | $188,726 | $2,264,709 | $13,883 | 92.6% | $68,977 | $105,865 | $539,972 |

- **Revenue:** subscriptions ($49 Solo / $249 Team / $999 Enterprise) plus metered overage runs. Month-1 revenue is $2,704; Month-24 revenue is $188,726.
- **Costs:** COGS = model tokens (measured v4 per-run token usage) + AWS Lambda attestation + Dodo Payments fees. OpEx = payroll, fixed cloud/observability and growth spend.
- **Runway:** starting cash is $150,000. EBITDA is negative until **Month 11**; the lowest projected cash balance is **$50,734 in Month 10**, after which the model is cash-flow positive. At the Month-10 burn of $2,736/month that buffer would cover about 19 more months if the customer ramp stalled, so the plan depends on hitting it.

---

## 5. Scenario Stress Test (`plan.xlsx → 4Q_Scenario_Comparison`)

This sheet uses its own static scenario assumptions (it is not a roll-up of the 24-month model). Q4 = Jul–Sep 2027. Annualised revenue = Q4 revenue × 4.

| Scenario | Q4 customers | Q4 runs | Q4 revenue | Annualised | Q4 COGS | Gross margin | Q4 EBITDA | Ending cash |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Main (Graph-Optimized Base Plan) | 145 | 137,958 | $192,462 | $769,848 | $16,278 | 91.5% | $104,184 | $207,995 |
| Growth (Ecosystem Attach Upside) | 240 | 229,206 | $319,576 | $1,278,306 | $23,792 | 92.6% | $212,984 | $419,198 |
| Downside (Unoptimized Grep + High Retry Burn) | 109 | 219,347 | $145,553 | $582,213 | $416,782 | -186.3% | $-343,229 | $-677,188 |

The downside scenario (no code-graph context, high retry burn) has COGS above revenue and runs out of cash in its first quarter
(Q1 ending cash $-24,547). That gap is the business case for the token reduction VeriFix measures in neatlogs.
