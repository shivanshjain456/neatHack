# VeriFix (`Team HyperX`) — Complete Step-by-Step Operator Checklist for Shivansh Jain

> **Goal**: Maximize your score across **100% of the neatHack 2026 judging rubric** (`30% Agent + 25% Partner Tools + 20% Demo Video + 15% Building in Public + 10% Originality & Usefulness`) + **$500 Community Prize**.

---

## 0. What Is Already 100% Done & Live (You Do NOT Need to Set These Up)

Everything below is already built, verified, and live:
- [x] **Public GitHub Repo (`shivanshjain456/neatHack`)**: Pushed and live at **`https://github.com/shivanshjain456/neatHack`** with `README.md`, `hackathon.md`, `BUSINESS_PLAN.md`, `plan.xlsx`, `REAL_OSS_BUG_REPORT_NEATLOGS.md`, and `docs/verifix_architecture_proof_loop.png`.
- [x] **Entire (`entire v0.11.4` + `entire-graph v0.4.0` + `entire-brain v0.1.0` + `entire-agent-verifix`)**:
  - 4 `Entire-Checkpoint` Git refs pushed to GitHub (`01M4J00GT6819W3DM06XE848DR`, `01M4J08RX867PFM4SNRE3GFCAR`, `01M4J6JRV5BHZJX6EH1HARAJG2`, `01M4J98Q5S510JRH4W3356YNXK`).
  - `benchmarks/graph.ndjson` (`1,635` lines) + Interactive Obsidian-style SVG Graph Visualizer in Mission Control.
  - `Entire Brain` (`385` symbols, `1,380` relations, durable facts) active.
  - Native `entire-agent-verifix` External Agent Protocol v1 plugin implemented and registered.
- [x] **Neatlogs (`neatlogs v1.4.26` SDK + Live MCP Server + 7 Custom Detections)**:
  - `7` active Detections (`246` 7-day flagged occurrences) and `3` remediated incidents live on `https://ingest.neatlogs.com` (Project ID `00201e50-a8c9-42cf-84bf-116568a49cd5`).
  - Controlled `v1` vs `v2` before/after proof (`-65.05%` prompt tokens, `-42.56%` latency, `27 -> 0` `Execution Failed` occurrences).
- [x] **Real Open-Source Bug Discovered, Fixed & Filed Upstream (`neatlogs/neatlogs#199`)**:
  - Live at **`https://github.com/neatlogs/neatlogs/issues/199`** (`30/30 -> 0/30` concurrent batch drops fixed, `530/530` unit tests passing).
- [x] **AWS Cloud Patch Attestation (`us-east-1`, Account `082229155652`)**:
  - Live AWS Lambda function `verifix-hyperx-patch-verifier` deployed in Team HyperX's official hackathon AWS account.
- [x] **cfo.ai Business Plan (`plan.xlsx` + `BUSINESS_PLAN.md` + Interactive Ari Sliders)**:
  - 4-tab formula-driven Excel workbook (`plan.xlsx`) + interactive Board Overview simulator in Mission Control (`-79.83%` unit COGS, `94.67%` Gross Margin, Infinite Runway).
- [x] **Live VeriFix Mission Control Server**: Running on port `8000` (`10/10` pytest tests + `6/6` jury self-test checks passing, `0` zero-tolerance violations).

---

## 1. What Is On YOU Right Now (Today — Saturday, Oct 10)

### Task A1: Publish Your First Build-in-Public Post + Reply on X (`15%` of Score + `$500` Community Prize)
**Why this is on you**: X requires posting from your personal X account (`#neatHack`). Because you do not have X Premium, every post below is strictly **under 280 characters**.

1. **Download the PNG diagram**:
   - In the file viewer (or from `https://github.com/shivanshjain456/neatHack/blob/main/docs/verifix_architecture_proof_loop.png`), download **`verifix_architecture_proof_loop.png`**.
2. **Open X (`https://x.com/compose/post`), attach `verifix_architecture_proof_loop.png`, and paste Post 1 (`273 / 280` chars)**:
   ```text
   Pointed VeriFix (Team HyperX) at @neatlogs SDK (v1.4.26) & found + fixed a real concurrency bug!

   • Shared _mask_pool drops 30/30 concurrent batches -> 0/30 fixed
   • 530/530 unit tests pass
   • Issue: https://github.com/neatlogs/neatlogs/issues/199
   #neatHack @EntireIO @cfo_ai
   ```
3. **Immediately reply to your own Post 1 with Post 2 (`227 / 280` chars)**:
   ```text
   Full repo, 4 @EntireIO Checkpoints, entire-agent-verifix plugin, 7 @neatlogs detections & @cfo_ai plan.xlsx:

   • -65.1% prompt tokens
   • -79.8% unit COGS ($0.1794/run)
   • Repo: https://github.com/shivanshjain456/neatHack
   #neatHack
   ```
4. **Copy the URL of your published X post and send it to me here in chat** so I can add it to the `Build log` and `Submission checklist` in `hackathon.md` and `README.md`.

---

### Task A2 (Optional 30-Second Power Move): Fork `neatlogs/neatlogs` So I Can Push a Live Pull Request for Issue `#199`
Right now, you already opened Issue **`https://github.com/neatlogs/neatlogs/issues/199`**. If we also open a **Pull Request** (`Fixes #199`) with our verified `530/530`-passing fix, Akshay Hangloo (`@akshay_hangloo`, Neatlogs founder & judge) will see both the issue and a ready-to-merge PR from Team HyperX!
1. Open **`https://github.com/neatlogs/neatlogs/fork`** in your browser while logged into `shivanshjain456`.
2. Click the green **"Create fork"** button (keep the repository name `neatlogs`).
3. Reply to me here: **`"I forked neatlogs"`** — your existing GitHub token already has permission on `shivanshjain456/*`, so **I will automatically push the branch and open the Pull Request for you!**

---

### Task A3 (Optional): Card-Free `cfo.ai` Workspace Activation via neatHack Organizers
Because `https://app.cfo.ai` asks for a card on the self-serve 14-day trial screen and you do not have a card:
- **Good news**: In the Intro Call (`00:54:51`), Siqi Chen (`@agent_wrapper`, Founder of `cfo.ai`) and Ajay (`@bettersayAJ`) explicitly demonstrated keeping `plan.xlsx` and `BUSINESS_PLAN.md` inside the Git repo with a `Board Overview` tab—which we have **already built and committed** (`/home/user/verifix/plan.xlsx` and `/home/user/verifix/BUSINESS_PLAN.md`).
- **Optional bonus**: If you are in the neatHack Discord/WhatsApp/email channel, you can message the `cfo.ai` support channel:
  > *"Hi @bettersayAJ / team — I'm Shivansh Jain (Team HyperX). I don't have a credit card to bypass the cfo.ai trial screen; can you activate the neatHack cfo.ai credits directly on my account email `<your-email>`?"*
- If they activate your account without a card, you can simply upload `/home/user/verifix/plan.xlsx` into `cfo.ai` (or give me a `cfo.ai` token) and take one screenshot. Even if they don't, your `plan.xlsx` + `BUSINESS_PLAN.md` + Mission Control Tab 4 simulator already cover 100% of the `cfo.ai` requirements.

---

## 2. What You Need to Provide Back to Me (Whenever Ready)

Here is the complete list of things you can paste back to me in this chat:
1. **Your published X post URL(s)** (after you post Task A1 above) -> I will embed them in `hackathon.md` and `README.md` as verified Build-in-Public evidence.
2. **`"I forked neatlogs"`** (if you click **"Create fork"** at `https://github.com/neatlogs/neatlogs/fork`) -> I will immediately push our verified fix branch to `https://github.com/shivanshjain456/neatlogs` and give you the 1-click Pull Request link (`Fixes #199`).
3. **(Optional) A second Google AI Studio `GEMINI_API_KEY`** from a second Google account (free, no card needed at `https://aistudio.google.com/apikey`) if you want extra daily rate-limit headroom when clicking live runs during your video recording.
4. **Your Demo Video URL** (Loom / YouTube / X video link once you record it) -> I will embed the link into `README.md` and `hackathon.md` and push the final commit before your submission quote-post.

---

## 3. What Is On YOU Tomorrow (Sunday, Oct 11 — Takes 5 Minutes)

### Task B1: Publish Build-in-Public Day 2 Post on X (`< 280` chars)
1. Open the **VeriFix Mission Control** live preview (port `8000`), click **Tab 3 (`Entire Graph Visualizer & Brain`)** and **Tab 4 (`cfo.ai Board Simulator & plan.xlsx`)**, and take 1–2 screenshots.
2. Post on X (`264 / 280` chars) with those screenshots attached:
   ```text
   Day 2 of #neatHack building VeriFix (Team HyperX):

   • Obsidian-style @EntireIO Graph blast-radius UI + Entire Brain memory
   • 7 @neatlogs custom detections (246 spans scored)
   • @cfo_ai game-engine Board Simulator + plan.xlsx

   https://github.com/shivanshjain456/neatHack
   ```
3. Send me the X post URL so I can log it in `hackathon.md`.

---

## 4. What Is On YOU for the Demo Video & Final Submission (Monday, Oct 12)

### Task C1: Record the ≤ 3-Minute Demo Video (`20%` of Total Score)
- **Hard Rule**: Must be **3 minutes or shorter (`≤ 3:00`)** — aim for **`2:35 – 2:50`**.
- **Tool**: Use **Loom**, **OBS Studio**, **macOS Screen Recording (`Cmd+Shift+5`)**, or **Windows Snipping Tool / Xbox Game Bar (`Win+G`)** with your microphone on.
- **Browser Tabs to Have Open Before Recording**:
  1. **Tab 1**: **VeriFix Mission Control** (live preview on port `8000`)
  2. **Tab 2**: **`https://github.com/shivanshjain456/neatHack`** (your public repo showing `README.md`, `plan.xlsx`, and 4 `Entire-Checkpoint` commits)
  3. **Tab 3**: **`https://github.com/neatlogs/neatlogs/issues/199`** (your live upstream bug report on `neatlogs/neatlogs`)
  4. **Tab 4**: **`https://app.neatlogs.com`** (your Neatlogs project showing traces & 7 Detections)

#### Exact 2:45 Minute Scene-by-Scene Script to Read While Clicking:
- **`0:00 – 0:35` (35s) — The Problem & Live Autonomous Fix (`Mission Control Tab 1`)**:
  > *"Hi, I'm Shivansh Jain from Team HyperX, and this is VeriFix—an autonomous bug-remediation agent that proves a patch won't break downstream callers before it commits. Standard coding agents grep for a failing function, make a local edit that passes the narrow bug test, and silently break 4 downstream callers. In VeriFix Mission Control, watch run `run_graph_case_01_le_80098`: on Attempt 1, a patch passes the local repro test (`1/1`), but VeriFix's Blast-Radius Guardrail catches a downstream caller regression (`2/3`), automatically rolls back the Git worktree, records the gotcha in Entire Brain, and self-heals on Attempt 2 (`1/1` repro + `3/3` caller contracts + AWS Lambda `us-east-1` SHA-256 attestation)."*
- **`0:35 – 1:20` (45s) — Partner #1: Entire (`Mission Control Tab 3` + GitHub Repo)**:
  > *"Here is how Entire powers VeriFix across four layers. First, inside Tab 3, our interactive Obsidian-style SVG Graph Visualizer renders the live `entire-graph` (`v0.4.0`) blast radius (`benchmarks/graph.ndjson`, 1,635 records)—clicking any node inspects its callers, callees, and sibling definitions. Second, `Entire Brain` (`v0.1.0`) recalls durable architectural invariants before planning and remembers every guardrail rollback. Third, we built `entire-agent-verifix`, a native Entire CLI External Agent Protocol v1 plugin. Fourth, every commit in our repo carries an `Entire-Checkpoint` trailer synced to `refs/entire/checkpoints/*`."*
- **`1:20 – 2:05` (45s) — Partner #2: Neatlogs (`Mission Control Tab 2 & Tab 5` + `neatlogs#199`)**:
  > *"Every workflow, retriever, tool, LLM, MCP, and guardrail span is traced in Neatlogs (`v1.4.26`). In Tab 2, our controlled `v1` vs `v2` experiment proves that replacing naive repo dumps with `entire-graph` localization cut prompt tokens by 65.05% (`12,216` to `4,269`) and latency by 42.56%. We also configured 7 active Neatlogs Detections (`246` flagged spans over 7 days), driving `Execution Failed` from 27 occurrences in `v1` down to 0 in `v2`. Even better: in Tab 5, we pointed VeriFix at the open-source `neatlogs` Python SDK itself, discovered a real thread-pool starvation bug in `masking_exporter.py` dropping 30 out of 30 concurrent batches, fixed it to 0/30 with 530/530 unit tests passing, and filed it upstream at `neatlogs/neatlogs#199`."*
- **`2:05 – 2:45` (40s) — Partner #3: cfo.ai (`Mission Control Tab 4` + `plan.xlsx`)**:
  > *"Finally, we connected live Neatlogs telemetry to our `cfo.ai` financial engine (`plan.xlsx` and `BUSINESS_PLAN.md`). In Tab 4, our interactive Ari Board Overview Simulator works like a game engine: dragging the growth, inference cost, or retry sliders—or toggling between `v1` and `v2`—recomputes ARR, Dodo Payments Merchant-of-Record fees (`3.9% + $0.40`), Gross Margin, and Runway in real time. Because `v2` cuts direct unit COGS by 79.83% (`$0.8896` down to `$0.1794/run`), VeriFix reaches a 94.67% Gross Margin, `$298K` Year-1 ARR (`$1.19M` Month-24 ARR in `plan.xlsx`), and cash-flow positive Infinite Runway by Month 4. Thank you!"*

---

### Task C2: Official Submission Window (Monday, Oct 12, 7:00 PM – 11:55 PM IST)
1. Between **7:00 PM IST and 11:55 PM IST on Monday, Oct 12, 2026**, go to `@neatlogs` on X and find their official **Submission Post**.
2. Click **Quote Post** (Repost with comment), attach your **≤ 3-minute Demo Video** (or link it), and paste this `< 280`-character submission text (`256 / 280` chars):
   ```text
   Official #neatHack submission — VeriFix (Team HyperX)!

   • @EntireIO Graph + Brain + entire-agent-verifix: -65.1% tokens
   • @neatlogs: 7 detections, 0% unguarded fails & neatlogs#199 fix
   • @cfo_ai plan.xlsx: -79.8% COGS, 94.7% GM

   https://github.com/shivanshjain456/neatHack
   ```
