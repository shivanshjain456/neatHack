import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export const C = {
  bg: "#0a120e",
  panel: "#0e1a14",
  panel2: "#12211a",
  ink: "#f2f6f1",
  sub: "#9db2a7",
  faint: "#6d8177",
  accent: "#4cc38a",
  accent2: "#8fe6bb",
  line: "rgba(255,255,255,0.14)",
  danger: "#ff7a70",
  warn: "#ffd166",
};

export const FONT = "Inter, system-ui, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif";
export const MONO = "'SF Mono', 'Cascadia Code', Menlo, Consolas, monospace";

export const useIn = (start: number, dur = 18, from = 26) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [start, start + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const y = interpolate(o, [0, 1], [from, 0]);
  return { opacity: o, transform: `translateY(${y}px)` };
};

export const useOut = (end: number, dur = 14) => {
  const f = useCurrentFrame();
  return interpolate(f, [end - dur, end], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
};

const MARK = (
  <div
    style={{
      width: 44,
      height: 48,
      background: "linear-gradient(160deg,#2f7a55,#1c4a34)",
      clipPath: "polygon(0 0,100% 0,100% 75%,50% 100%,0 75%)",
      display: "grid",
      placeItems: "center",
      color: "#eafff3",
      fontSize: 26,
      fontWeight: 600,
    }}
  >
    ✓
  </div>
);

export const Chrome: React.FC<{ index: string; section: string; progress: number }> = ({ index, section, progress }) => (
  <>
    <div style={{ position: "absolute", top: 44, left: 64, display: "flex", alignItems: "center", gap: 14 }}>
      {MARK}
      <span style={{ color: C.ink, fontWeight: 700, fontSize: 26, letterSpacing: "-0.5px" }}>
        VeriFix<span style={{ color: C.accent }}>.</span>
      </span>
    </div>
    <div style={{ position: "absolute", top: 50, right: 64, textAlign: "right" }}>
      <div style={{ color: C.faint, fontSize: 19, letterSpacing: "3px", fontWeight: 600 }}>{index}</div>
      <div style={{ color: C.sub, fontSize: 17, marginTop: 4 }}>{section}</div>
    </div>
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 4, background: "rgba(255,255,255,0.07)" }}>
      <div style={{ height: "100%", width: `${progress * 100}%`, background: `linear-gradient(90deg,${C.accent},${C.accent2})` }} />
    </div>
  </>
);

export const Bg: React.FC<{ glow?: string }> = ({ glow = "18% 22%" }) => {
  const f = useCurrentFrame();
  const drift = interpolate(f, [0, 600], [0, 60], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(900px 600px at ${glow}, rgba(76,195,138,0.10), transparent 60%)`,
          transform: `translateY(${-drift * 0.2}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.5,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
          backgroundSize: "72px 72px",
        }}
      />
    </AbsoluteFill>
  );
};

export const Eyebrow: React.FC<{ children: React.ReactNode; at?: number; tone?: string }> = ({ children, at = 0, tone = C.accent }) => (
  <div style={{ ...useIn(at), display: "flex", alignItems: "center", gap: 16 }}>
    <div style={{ width: 34, height: 2, background: tone }} />
    <span style={{ color: tone, fontSize: 24, letterSpacing: "6px", fontWeight: 700 }}>{children}</span>
  </div>
);

export const H1: React.FC<{ children: React.ReactNode; at?: number; size?: number; max?: number }> = ({ children, at = 6, size = 78, max = 1500 }) => (
  <div style={{ ...useIn(at), color: C.ink, fontSize: size, fontWeight: 700, letterSpacing: "-2.5px", lineHeight: 1.12, maxWidth: max }}>{children}</div>
);

export const Body: React.FC<{ children: React.ReactNode; at?: number; size?: number; max?: number }> = ({ children, at = 14, size = 32, max = 1400 }) => (
  <div style={{ ...useIn(at), color: C.sub, fontSize: size, lineHeight: 1.55, maxWidth: max, fontWeight: 400 }}>{children}</div>
);

export const Accent: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span style={{ color: C.accent2, fontWeight: 600 }}>{children}</span>
);

export const Count: React.FC<{ to: number; at?: number; dur?: number; fmt?: (n: number) => string; size?: number; color?: string }> = ({
  to,
  at = 10,
  dur = 40,
  fmt = (n) => `${Math.round(n)}`,
  size = 120,
  color = C.ink,
}) => {
  const f = useCurrentFrame();
  const v = interpolate(f, [at, at + dur], [0, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <span style={{ color, fontSize: size, fontWeight: 750, letterSpacing: "-3px", fontVariantNumeric: "tabular-nums" }}>{fmt(v)}</span>;
};

export const Card: React.FC<{ children: React.ReactNode; at?: number; w?: number | string; pad?: number; tone?: string }> = ({
  children,
  at = 10,
  w,
  pad = 34,
  tone = C.line,
}) => (
  <div
    style={{
      ...useIn(at),
      background: "rgba(14,26,20,0.85)",
      border: `1px solid ${tone}`,
      borderRadius: 20,
      padding: pad,
      width: w,
      boxShadow: "0 20px 60px rgba(0,0,0,0.35)",
    }}
  >
    {children}
  </div>
);

export const Pad: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ display: "flex", flexDirection: "column", justifyContent: "center", paddingLeft: 110, paddingRight: 110, gap: 34 }}>
    {children}
  </AbsoluteFill>
);
