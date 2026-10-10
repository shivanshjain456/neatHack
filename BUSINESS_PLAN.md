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

## 2. Measured Telemetry Drivers (`v1` Before Fix vs. `v2` After Fix)

Every unit-cost assumption in `plan.xlsx` (`Assumptions!C13:C20`) is grounded in live experiments (`exp_0e3f5ca743`) traced in Neatlogs (`Project ID: 00201e50-a8c9-42cf-84bf-116568a49cd5`):

| Telemetry Driver | `v1` Baseline (`baseline_naive`) | `v2` Graph-Guarded (`entire-graph`) | Measured Improvement | Financial Impact on Unit Economics |
| :--- | :---: | :---: | :---: | :--- |
| **Prompt Tokens / Run** | `12,216` | **`4,269`** | **`-65.05%`** | Eliminates 7,947 wasted context tokens per run |
| **Completion Tokens / Run** | `2,179` | **`953`** | **`-56.26%`** | Focused caller-contract synthesis |
| **Total Tokens / Run** | `14,395` | **`5,222`** | **`-63.72%`** | Nearly 3x more remediations per LLM quota dollar |
| **End-to-End Latency** | `20,743.55 ms` | **`11,914.84 ms`** | **`-42.56%`** | 42.6% faster sandbox + AWS Lambda verification |
| **Modeled Enterprise COGS / Run** | `$0.8896` | **`$0.1794`** | **`-79.83%`** | Turns Pro tier from **`-21.7%` loss** into **`+79.7%` gross margin** |
| **Measured Gemini Flash + Lambda COGS** | `$0.01105` | **`$0.00568`** | **`-48.60%`** | Delivers **`99.08%`** gross margin on Flash workloads |

---

## 3. Pricing Architecture & Dodo Payments Merchant-of-Record Integration

VeriFix monetizes via a hybrid **SaaS Seat/Repo Subscription + Verified Remediation Overage** model billed globally through **Dodo Payments** (`3.9% + $0.40` Merchant-of-Record fee handling global VAT/GST and usage metering):

| Tier | Monthly Price | Included Verified Runs | Overage / Extra Verified Run | Target Customer Profile | Gross Margin (`v2` Flash) | Gross Margin (`v2` Enterprise Frontier) |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: |
| **Solo Pro** | **`$49 / mo`** | `100 runs/mo` | `$0.60 / run` | Independent engineers & solo founders | `99.1%` | `79.7%` *(vs `-21.7%` in `v1`!)* |
| **Team Guarded** | **`$249 / mo`** | `600 runs/mo` | `$0.45 / run` | 5–15 engineer product teams with CI gates | `98.9%` | `78.4%` |
| **Enterprise VPC** | **`$999 / mo`** | `3,000 runs/mo` | `$0.35 / run` | Regulated fintech/cloud orgs (`us-east-1` VPC) | `98.6%` | `75.8%` |

---

## 4. 24-Month Deterministic Trajectory (`plan.xlsx -> 24M_Main_Model`)

Starting with **`$150,000`** in initial capital reserve (`Assumptions!C3`):
- **Month 1 (Launch)**: `18` paying customers (`14 Solo`, `3 Team`, `1 Enterprise`), `4,038` verified runs/mo, **`$2,664` MRR** (`$31,968` ARR).
- **Month 4 (Cash-Flow Break-Even)**: Crosses positive monthly EBITDA as Team & Enterprise cohorts compound.
- **Month 12 (Year 1 Exit)**: `167` paying customers (`117 Solo`, `43 Team`, `7 Enterprise`), `47,384` verified runs/mo, **`$26,997` MRR** (**`$323,964` ARR**), **`89.2%` Gross Margin**, **`$192,410` Ending Cash**.
- **Month 24 (Year 2 Exit)**: `839` paying customers (`643 Solo`, `183 Team`, `13 Enterprise`), `172,416` verified runs/mo, **`$99,369` MRR** (**`$1,192,428` ARR**), **`89.5%` Gross Margin**, **`$584,120` Ending Cash**, **`UNLIMITED (Cash-Flow Positive)` Runway**.

---

## 5. Multi-Scenario Stress Test (`4Q_Scenario_Comparison`)

| Scenario | Q4 Exit ARR | Q4 Gross Margin % | Q4 Net Burn / EBITDA | Q4 Ending Cash | Runway Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. `Main` (Base Telemetry-Grounded)** | **`$298,050`** | **`94.67%`** | **`+$24,992 / qtr`** | **`$174,804`** | **Cash-Flow Positive (Infinite Runway)** |
| **2. `Growth` (Viral PLG + GitHub Marketplace)** | **`$547,423`** | **`94.68%`** | **`+$74,978 / qtr`** | **`$248,690`** | **Cash-Flow Positive (Infinite Runway)** |
| **3. `Downside` (Enterprise High-Retry + Frontier LLM Pricing)** | **`$160,673`** | **`75.60%`** | **`-$18,918 / qtr`** | **`$39,144`** | **`6.2 Months` Runway (Protected by `entire-graph` `-79.83%` COGS cut)** |
