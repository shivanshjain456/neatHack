import puppeteer from "puppeteer-core";
import path from "path";
import fs from "fs";

const OUT_DIR = path.resolve("/home/user/verifix/video/public/captures");
fs.mkdirSync(OUT_DIR, { recursive: true });

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: "/usr/bin/chromium",
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--window-size=1920,1080",
    ],
    defaultViewport: {
      width: 1920,
      height: 1080,
      deviceScaleFactor: 1,
    },
  });

  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:8000", { waitUntil: "networkidle0" });
  await page.waitForFunction(
    () => document.getElementById("kpiRuns")?.textContent !== "-",
    { timeout: 15000 }
  );
  await sleep(600);

  // 1. Tab 1: Select run_graph_case_01_le_3061 (Caller-Trap Rollback & Recovery)
  await page.evaluate(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    switchTab("tab-runs", document.getElementById("tabBtn-runs"));
    selectRun("run_graph_case_01_le_3061");
  });
  await sleep(800);
  await page.screenshot({
    path: path.join(OUT_DIR, "01_tab1_run3061_recovery.png"),
    fullPage: false,
  });

  // 2. Tab 1: Scrolled to show the 7-step execution ledger, hypotheses, patches & unified diff
  await page.evaluate(() => window.scrollTo({ top: 480, behavior: "instant" }));
  await sleep(600);
  await page.screenshot({
    path: path.join(OUT_DIR, "02_tab1_steps_and_diff.png"),
    fullPage: false,
  });

  // 3. Tab 3: Entire Graph Visualizer, Checkpoints & Brain (Top view: SVG graph + Brain + Plugin)
  await page.evaluate(async () => {
    window.scrollTo({ top: 0, behavior: "instant" });
    switchTab("tab-entire", document.getElementById("tabBtn-entire"));
    document.getElementById("symbolInput").value = "calculate_tiered_fee";
    await inspectGraphSymbol();
  });
  await sleep(700);
  await page.screenshot({
    path: path.join(OUT_DIR, "03_tab3_entire_graph_and_brain.png"),
    fullPage: false,
  });

  // 4. Tab 3: Scrolled to live Entire Checkpoints (`entire checkpoint explain HEAD`, `tokens`, `why`)
  await page.evaluate(() => window.scrollTo({ top: 820, behavior: "instant" }));
  await sleep(700);
  await page.screenshot({
    path: path.join(OUT_DIR, "04_tab3_entire_checkpoints_and_why.png"),
    fullPage: false,
  });

  // 5. Tab 2: Before/After Experiment & Neatlogs MCP + 11 Active Detections
  await page.evaluate(async () => {
    window.scrollTo({ top: 0, behavior: "instant" });
    switchTab("tab-experiment", document.getElementById("tabBtn-experiment"));
    await loadNeatlogsMCP();
  });
  await sleep(1200);
  await page.screenshot({
    path: path.join(OUT_DIR, "05_tab2_neatlogs_experiment_and_mcp.png"),
    fullPage: false,
  });

  // 6. Tab 4: cfo.ai Ari Simulator, plan.xlsx & 4-Quarter Scenarios
  await page.evaluate(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    switchTab("tab-cfo", document.getElementById("tabBtn-cfo"));
    updateAriSimulation();
  });
  await sleep(900);
  await page.screenshot({
    path: path.join(OUT_DIR, "06_tab4_cfo_ai_simulator_and_plan_xlsx.png"),
    fullPage: false,
  });

  // 7. Tab 5: Real OSS Bug Hunt (neatlogs#199 & PR #203) & 6/6 Jury Self-Test
  await page.evaluate(async () => {
    window.scrollTo({ top: 0, behavior: "instant" });
    switchTab("tab-oss", document.getElementById("tabBtn-oss"));
    await runBrowserSelftest();
    await runOSSConcurrencyBenchmark();
  });
  await sleep(1200);
  await page.screenshot({
    path: path.join(OUT_DIR, "07_tab5_oss_bug_hunt_and_selftest.png"),
    fullPage: false,
  });

  await browser.close();
  console.log("Captured 7 live 1920x1080 product screenshots from http://127.0.0.1:8000");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
