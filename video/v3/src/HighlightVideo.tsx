import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { C, FONT, Bg, Chrome, Eyebrow, H1, Body, Accent, Count, Card, Pad } from "./theme";

const Frame: React.FC<{ index: string; section: string; children: React.ReactNode }> = ({ index, section, children }) => (
  <AbsoluteFill style={{ fontFamily: FONT }}>
    <Bg glow="70% 30%" />
    {children}
    <Chrome index={index} section={section} progress={0} />
  </AbsoluteFill>
);

const Hook: React.FC = () => (
  <Frame index="01" section="VERIFIX">
    <Pad>
      <Eyebrow at={2}>NEATHACK 2026</Eyebrow>
      <H1 at={8} size={96}>Coding agents say “fixed.”<br />VeriFix <Accent>proves</Accent> it.</H1>
    </Pad>
  </Frame>
);

const Trap: React.FC = () => (
  <Frame index="02" section="THE PROOF">
    <Pad>
      <Eyebrow at={2} tone={C.warn}>CALLER TRAP · LIVE</Eyebrow>
      <H1 at={6} size={70}>A patch passes the bug’s test<br />but breaks two callers…</H1>
      <div style={{ display: "flex", gap: 26, marginTop: 30 }}>
        <Card at={50} pad={26} tone={C.danger}><div style={{ color: C.danger, fontWeight: 700, fontSize: 26 }}>caught ✗✗</div></Card>
        <Card at={80} pad={26} tone={C.warn}><div style={{ color: C.warn, fontWeight: 700, fontSize: 26 }}>rolled back</div></Card>
        <Card at={110} pad={26} tone={C.accent}><div style={{ color: C.accent, fontWeight: 700, fontSize: 26 }}>re-verified ✓</div></Card>
      </div>
    </Pad>
  </Frame>
);

const Numbers: React.FC = () => (
  <Frame index="03" section="THE NUMBERS">
    <Pad>
      <Eyebrow at={2}>CONTROLLED · 60 RUNS</Eyebrow>
      <div style={{ display: "flex", gap: 60, alignItems: "baseline" }}>
        <div><Count to={62} at={10} fmt={(n) => `${Math.round(n)}%`} size={140} color={C.accent2} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>fewer tokens</div></div>
        <div><Count to={20} at={40} fmt={(n) => `${Math.round(n)}/20`} size={140} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>judged fixes</div></div>
        <div><Count to={24} at={70} fmt={(n) => `${Math.round(n)}/24`} size={140} /><div style={{ color: C.sub, fontSize: 26, marginTop: 6 }}>injections shipped: 0</div></div>
      </div>
    </Pad>
  </Frame>
);

const Close: React.FC = () => (
  <Frame index="04" section="CHECK IT">
    <Pad>
      <Eyebrow at={2}>VERIFY EVERY CLAIM</Eyebrow>
      <H1 at={8} size={84}>Evidence, <Accent>linked</Accent>.</H1>
      <Body at={50} size={30} >github.com/shivanshjain456/neatHack · #neatHack</Body>
    </Pad>
  </Frame>
);

const SEGS: { dur: number; Comp: React.FC }[] = [
  { dur: 150, Comp: Hook },
  { dur: 300, Comp: Trap },
  { dur: 240, Comp: Numbers },
  { dur: 210, Comp: Close },
];

export const HIGHLIGHT_FRAMES = SEGS.reduce((a, s) => a + s.dur, 0);

export const HighlightVideo: React.FC = () => {
  let acc = 0;
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      {SEGS.map(({ dur, Comp }, i) => {
        const from = acc;
        acc += dur;
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <Comp />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
