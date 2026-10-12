import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, interpolate, staticFile } from "remotion";
import { C, FONT, MONO, Bg, Chrome, Eyebrow, H1, Body, Accent, Count, Card, Pad, useIn } from "./theme";

const S: { dur: number; Comp: React.FC<{ p: (f: number) => number }> }[] = [];

const Frame: React.FC<{ index: string; section: string; children: React.ReactNode }> = ({ index, section, children }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ fontFamily: FONT }}>
      <Bg />
      {children}
      <Chrome index={index} section={section} progress={0} />
    </AbsoluteFill>
  );
};

/* 01 — Hook */
S.push({ dur: 300, Comp: () => (
  <Frame index="01" section="THE PROBLEM">
    <Pad>
      <Eyebrow at={4}>NEATHACK 2026 · TEAM HYPERX</Eyebrow>
      <H1 at={12} size={92}>Coding agents say <Accent>“fixed.”</Accent></H1>
      <H1 at={70} size={92}>VeriFix has to <span style={{ color: C.accent }}>prove</span> it.</H1>
      <Body at={130} size={30}>An autonomous remediation agent that is not allowed to ship a patch<br />until it has proved the fix breaks nothing else.</Body>
    </Pad>
  </Frame>
) });

/* 02 — Problem */
const Caller = ({ name, ok, at }: { name: string; ok: boolean; at: number }) => {
  const st = useIn(at);
  return (
    <div style={{ ...st, display: "flex", alignItems: "center", gap: 18, padding: "18px 26px", border: `1px solid ${ok ? "rgba(76,195,138,.4)" : "rgba(255,122,112,.4)"}`, borderRadius: 14, background: "rgba(255,255,255,0.03)" }}>
      <span style={{ fontFamily: MONO, color: C.ink, fontSize: 26 }}>{name}</span>
      <span style={{ marginLeft: "auto", fontSize: 28, color: ok ? C.accent : C.danger, fontWeight: 700 }}>{ok ? "✓" : "✗"}</span>
    </div>
  );
};
S.push({ dur: 480, Comp: () => (
  <Frame index="02" section="WHY IT MATTERS">
    <Pad>
      <Eyebrow at={2}>SILENT REGRESSIONS</Eyebrow>
      <H1 at={8} size={72}>The test passed.<br />The system broke.</H1>
      <div style={{ display: "flex", gap: 40, alignItems: "stretch", marginTop: 26 }}>
        <Card at={40} w={700}>
          <div style={{ color: C.sub, fontSize: 22, letterSpacing: 2, fontWeight: 700 }}>A “fix” to <span style={{ fontFamily: MONO, color: C.ink }}>calculate_tiered_fee</span></div>
          <div style={{ fontFamily: MONO, fontSize: 26, color: C.accent2, marginTop: 20 }}>own test&nbsp;&nbsp;<span style={{ color: C.accent, fontWeight: 700 }}>✓ passes</span></div>
          <Body at={70} size={26}>Confident. Shipped. And wrong everywhere else.</Body>
        </Card>
        <div style={{ display: "flex", flexDirection: "column", gap: 18, justifyContent: "center", flex: 1 }}>
          <Caller name="build_settlement_batch" ok={false} at={90} />
          <Caller name="render_tax_invoice" ok={false} at={110} />
          <Body at={140} size={26}>Two downstream callers now fail — and nothing in the agent’s own check said so.</Body>
        </div>
      </div>
    </Pad>
  </Frame>
) });

/* 03 — Thesis */
S.push({ dur: 360, Comp: () => (
  <Frame index="03" section="THE THESIS">
    <Pad>
      <Eyebrow at={2}>BLAST-RADIUS-AWARE VERIFICATION</Eyebrow>
      <H1 at={8} size={80}>Not “does the test pass?”<br />“does <Accent>everything</Accent> still pass?”</H1>
      <div style={{ display: "flex", gap: 24, marginTop: 30 }}>
        {["Map the blast radius", "Verify every caller", "Roll back on regression"].map((t, i) => (
          <Card key={t} at={60 + i * 20} w={440} pad={28}><div style={{ color: C.ink, fontSize: 30, fontWeight: 650 }}>{`0${i + 1}  ${t}`}</div></Card>
        ))}
      </div>
    </Pad>
  </Frame>
) });

/* 04 — Pipeline */
const STEPS = [
  ["Entire Graph", "find every caller before editing"],
  ["Reproduce", "failing test, isolated worktree"],
  ["Synthesize", "surgical patch, minimal diff"],
  ["Verify", "repro + ALL caller tests"],
  ["Roll back", "on any regression, feed the planner"],
  ["Certify", "verification certificate + trace"],
];
S.push({ dur: 720, Comp: () => (
  <Frame index="04" section="HOW IT WORKS">
    <Pad>
      <Eyebrow at={2}>THE PIPELINE</Eyebrow>
      <H1 at={6} size={64}>One loop, six gates.</H1>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 26, marginTop: 26 }}>
        {STEPS.map(([t, s], i) => (
          <Card key={t} at={40 + i * 60} pad={30}>
            <div style={{ color: C.accent, fontFamily: MONO, fontSize: 24 }}>{`0${i + 1}`}</div>
            <div style={{ color: C.ink, fontSize: 34, fontWeight: 700, marginTop: 8 }}>{t}</div>
            <div style={{ color: C.sub, fontSize: 24, marginTop: 8 }}>{s}</div>
          </Card>
        ))}
      </div>
    </Pad>
  </Frame>
) });

/* 05 — Caller trap */
const TrapState = ({ t, tone, at, badge }: { t: string; tone: string; at: number; badge: string }) => (
  <Card at={at} pad={26} tone={tone} w={300}>
    <div style={{ color: tone, fontSize: 20, letterSpacing: 2, fontWeight: 700 }}>{badge}</div>
    <div style={{ color: C.ink, fontSize: 26, fontWeight: 600, marginTop: 10 }}>{t}</div>
  </Card>
);
S.push({ dur: 660, Comp: () => (
  <Frame index="05" section="LIVE PROOF · CALLER TRAP">
    <Pad>
      <Eyebrow at={2} tone={C.warn}>FAULT INJECTION</Eyebrow>
      <H1 at={6} size={60}>We plant a patch that passes the bug’s test<br />but breaks two callers. Watch what happens.</H1>
      <div style={{ display: "flex", gap: 22, alignItems: "stretch", marginTop: 30 }}>
        <TrapState badge="ATTEMPT 1" tone={C.warn} at={60} t="own test ✓" />
        <TrapState badge="CALLERS" tone={C.danger} at={100} t="2 callers ✗" />
        <TrapState badge="GUARDRAIL" tone={C.danger} at={150} t="regression caught → roll back" />
        <TrapState badge="ATTEMPT 2" tone={C.accent} at={220} t="bug fixed, callers pass" />
        <TrapState badge="CERTIFICATE" tone={C.accent} at={280} t="verified, traced, attested" />
      </div>
      <Body at={340} size={28}>2 attempts · 1 rollback · every step traced in neatlogs. Reproducible live from the Verify screen.</Body>
    </Pad>
  </Frame>
) });

/* 06 — Experiment */
S.push({ dur: 600, Comp: () => (
  <Frame index="06" section="EVIDENCE · CONTROLLED EXPERIMENT">
    <Pad>
      <Eyebrow at={2}>3 ARMS · 4 CASES · 5 REPEATS · INDEPENDENT JUDGE</Eyebrow>
      <H1 at={6} size={64}>Same model, same prompt.<br />Only the context differs.</H1>
      <div style={{ display: "flex", gap: 40, marginTop: 34, alignItems: "baseline" }}>
        <div><Count to={62} at={40} fmt={(n) => `${Math.round(n)}%`} size={150} color={C.accent2} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>fewer tokens than<br />reading the whole repo</div></div>
        <div><Count to={20} at={70} fmt={(n) => `${Math.round(n)}/20`} size={150} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>passed the<br />independent judge</div></div>
        <div><Count to={5} at={100} fmt={(n) => `${Math.round(n)}/5`} size={150} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>planted regressions<br />caught & rolled back</div></div>
      </div>
      <Body at={150} size={26}>95% CI by case 58–68% · sign test p = 0.00004 · recomputed from 60 raw runs by <span style={{ fontFamily: MONO, color: C.ink }}>verify_claims.py</span></Body>
    </Pad>
  </Frame>
) });

/* 07 — Assurance */
S.push({ dur: 540, Comp: () => (
  <Frame index="07" section="PASSING TESTS IS NOT PROOF">
    <Pad>
      <Eyebrow at={2}>PATCH ASSURANCE · 15 GATES</Eyebrow>
      <H1 at={6} size={64}>Tests are where checking <Accent>starts</Accent>.</H1>
      <div style={{ display: "flex", gap: 30, marginTop: 30 }}>
        <Card at={50} w={640}><div style={{ color: C.sub, fontSize: 24, fontWeight: 700, letterSpacing: 2 }}>C9 · MUTANTS THAT PASS EVERY TEST</div>
          <div style={{ marginTop: 16 }}><Count to={84} fmt={(n) => `${Math.round(n)}%`} size={100} color={C.accent2} /></div>
          <Body at={90} size={26}>of wrong-but-test-passing mutants caught (21/25) · 0/18 false blocks</Body></Card>
        <Card at={90} w={640}><div style={{ color: C.sub, fontSize: 24, fontWeight: 700, letterSpacing: 2 }}>C10 · PROMPT INJECTION</div>
          <div style={{ marginTop: 16 }}><Count to={24} fmt={(n) => `${Math.round(n)}/24`} size={100} color={C.accent2} /></div>
          <Body at={130} size={26}>injected payloads shipped: zero (Fisher p = 0.0094). Undefended baseline shipped 7/24.</Body></Card>
      </div>
    </Pad>
  </Frame>
) });

/* 08 — neatlogs + OSS */
S.push({ dur: 540, Comp: () => (
  <Frame index="08" section="PARTNER · NEATLOGS">
    <Pad>
      <Eyebrow at={2}>EVERY RUN TRACED</Eyebrow>
      <H1 at={6} size={64}>neatlogs sees every model call,<br />token and cost.</H1>
      <div style={{ display: "flex", gap: 40, marginTop: 30, alignItems: "baseline" }}>
        <div><Count to={1400} at={40} fmt={(n) => `${Math.round(n).toLocaleString()}+`} size={120} color={C.accent2} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>traces, read back<br />over the neatlogs MCP</div></div>
        <Body at={90} size={28} max={900}>And it paid for itself: tracing surfaced telemetry being dropped under load in the neatlogs SDK itself → filed <Accent>issue #199</Accent>, opened <Accent>PR #203</Accent> with the fix.</Body>
      </div>
    </Pad>
  </Frame>
) });

/* 08b — neatlogs critical incidents */
S.push({ dur: 480, Comp: () => (
  <Frame index="08+" section="NEATLOGS · CRITICAL INCIDENTS">
    <Pad>
      <Eyebrow at={2}>CRITICAL INCIDENTS · IDENTIFIED, INVESTIGATED, RESOLVED</Eyebrow>
      <H1 at={6} size={58}>neatlogs flagged the incidents.<br />The traces resolved them.</H1>
      <div style={{ display: "flex", gap: 34, marginTop: 26, alignItems: "stretch" }}>
        <img src={staticFile("nl-incidents.png")} style={{ width: 860, height: "auto", borderRadius: 14, border: "1px solid rgba(255,255,255,.15)" }} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 22 }}>
          <Body at={50} size={26}>Quota-429 cascade flagged → <Accent>failover detector</Accent> shipped (111 occurrences).</Body>
          <Body at={95} size={26}>Execution-failed spike (52) → root-caused in the investigate view.</Body>
          <Body at={140} size={26}>Dropped SDK telemetry → <Accent>issue #199</Accent> + <Accent>PR #203</Accent>.</Body>
        </div>
      </div>
    </Pad>
  </Frame>
) });

/* 09 — Entire */
S.push({ dur: 420, Comp: () => (
  <Frame index="09" section="PARTNER · ENTIRE">
    <Pad>
      <Eyebrow at={2}>ENTIRE GRAPH + CHECKPOINTS</Eyebrow>
      <H1 at={6} size={64}>Entire tells the agent what its<br />change could <Accent>break</Accent>.</H1>
      <Body at={60} size={30}>At runtime, Entire Graph supplies the caller list the guardrail tests. In development, 24 checkpoints record how VeriFix itself was built.</Body>
    </Pad>
  </Frame>
) });

/* 10 — cfo */
S.push({ dur: 420, Comp: () => (
  <Frame index="10" section="PARTNER · CFO.AI">
    <Pad>
      <Eyebrow at={2}>BUSINESS PLAN FROM MEASURED TOKENS</Eyebrow>
      <H1 at={6} size={64}>cfo.ai turns traced cost into a<br />24-month model.</H1>
      <div style={{ display: "flex", gap: 40, marginTop: 26, alignItems: "baseline" }}>
        <div><Count to={11} at={50} fmt={(n) => `M${Math.round(n)}`} size={120} color={C.accent2} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>first positive EBITDA</div></div>
        <div><Count to={2.26} at={80} fmt={(n) => `$${n.toFixed(2)}M`} size={120} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>Month-24 ARR (projection)</div></div>
      </div>
      <Body at={120} size={24}>All figures are projections, recomputed by scripts/compute_plan_values.py; a test fails on drift.</Body>
    </Pad>
  </Frame>
) });

/* 11 — supply chain */
S.push({ dur: 360, Comp: () => (
  <Frame index="11" section="RIGOR · SUPPLY CHAIN">
    <Pad>
      <Eyebrow at={2}>VERIFIX APPLIES ITS OWN MEDICINE</Eyebrow>
      <H1 at={6} size={60}>Hash-locked deps · SBOM · SLSA provenance.<br />Byte-reproducible builds.</H1>
      <Body at={70} size={28}>Every release is signed and verified before deploy. 170 deterministic tests + 18 real agent runs gate each commit.</Body>
    </Pad>
  </Frame>
) });

/* 12 — close */
S.push({ dur: 360, Comp: () => (
  <Frame index="12" section="CHECK IT YOURSELF">
    <Pad>
      <Eyebrow at={2}>VERIFY EVERY CLAIM IN TWO MINUTES</Eyebrow>
      <H1 at={8} size={84}>Every number links<br />to its <Accent>evidence</Accent>.</H1>
      <div style={{ display: "flex", gap: 26, marginTop: 34 }}>
        <Card at={60} pad={28}><div style={{ color: C.accent, fontSize: 24, fontWeight: 700 }}>VERIFY</div><div style={{ fontFamily: MONO, color: C.ink, fontSize: 26, marginTop: 8 }}>…/neatHack/#verify</div></Card>
        <Card at={90} pad={28}><div style={{ color: C.accent, fontSize: 24, fontWeight: 700 }}>SOURCE</div><div style={{ fontFamily: MONO, color: C.ink, fontSize: 26, marginTop: 8 }}>github.com/shivanshjain456/neatHack</div></Card>
      </div>
      <Body at={140} size={28}>VeriFix · Team HyperX · #neatHack</Body>
    </Pad>
  </Frame>
) });

export const FULL_FRAMES = S.reduce((a, s) => a + s.dur, 0);

/* F3-compliant submission cut: uniform scale so the cut is exactly 5,340 frames = 178.0 s (<= 180 s cap). */
const FULL_TOTAL = S.reduce((a, s) => a + s.dur, 0);
export const SUB_DURS = S.map((s) => Math.round((s.dur * 5340) / FULL_TOTAL));
export const SUBMISSION_FRAMES = SUB_DURS.reduce((a, b) => a + b, 0);

const makeComp = (durs: number[]) => () => {
  let acc = 0;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      {S.map(({ Comp }, i) => {
        const d = durs[i];
        const from = acc;
        acc += d;
        return (
          <Sequence key={i} from={from} durationInFrames={d}>
            <Comp p={() => 0} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export const FullVideo = makeComp(S.map((s) => s.dur));
export const SubmissionVideo = makeComp(SUB_DURS);
