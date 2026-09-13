import React from "react";
import { AbsoluteFill, Audio, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont as loadSans } from "@remotion/google-fonts/NotoSansTC";
import { loadFont as loadSerif } from "@remotion/google-fonts/NotoSerifTC";
import { T } from "./theme";
import { nar, SegId, sec } from "./timeline";

const sans = loadSans("normal", { weights: ["400", "500", "700"] }).fontFamily;
const serif = loadSerif("normal", { weights: ["600", "700"] }).fontFamily;
export const FONT = { sans: `${sans}, 'Noto Sans TC', sans-serif`, serif: `${serif}, 'Noto Serif TC', serif`, mono: "'JetBrains Mono', ui-monospace, monospace" };

export const Page: React.FC<{ children: React.ReactNode; bg?: string }> = ({ children, bg = T.paper }) => (
  <AbsoluteFill style={{ background: bg, fontFamily: FONT.sans, color: T.ink }}>{children}</AbsoluteFill>
);

/** 旁白音軌＋底部字幕（依句號切段，依時間比例輪播） */
export const Narration: React.FC<{ id: SegId; from?: number }> = ({ id, from = 0 }) => {
  const frame = useCurrentFrame();
  const n = nar(id); const total = sec(n.duration);
  // 字幕顯示 subtitle（阿拉伯數字），每句時長權重用口白 text（中文數字，字數≈語音長度）；句數不一致時退回用字幕本身
  const split = (t: string) => t.split(/(?<=[。！？])/).filter((s) => s.trim());
  const spoken = split(n.text); const parts = split((n as { subtitle?: string }).subtitle ?? n.text);
  const weights = (spoken.length === parts.length ? spoken : parts).map((p) => p.length); const sum = weights.reduce((a, b) => a + b, 0);
  const t = frame - from; let acc = 0; let cur = parts[parts.length - 1];
  for (let i = 0; i < parts.length; i++) { const w = (weights[i] / sum) * total; if (t < acc + w) { cur = parts[i]; break; } acc += w; }
  const visible = t >= 0 && t < total + 8;
  return (
    <>
      <Audio src={staticFile(`tts/${id}.wav`)} startFrom={0} />
      {visible && (
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 44, display: "flex", justifyContent: "center", pointerEvents: "none" }}>
          <div style={{ maxWidth: 1500, background: "rgba(6,62,51,.86)", color: "#fff", fontSize: 34, lineHeight: 1.5, padding: "12px 28px", borderRadius: 10, letterSpacing: 0.5, textAlign: "center" }}>{cur}</div>
        </div>
      )}
    </>
  );
};

export const FadeIn: React.FC<{ children: React.ReactNode; delay?: number; y?: number; style?: React.CSSProperties }> = ({ children, delay = 0, y = 24, style }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const p = spring({ frame: frame - delay, fps, config: { damping: 200, stiffness: 120 } });
  return <div style={{ opacity: p, transform: `translateY(${(1 - p) * y}px)`, ...style }}>{children}</div>;
};

export const Eyebrow: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ color: T.sage, fontSize: 24, letterSpacing: 3, fontWeight: 500, marginBottom: 18 }}>{children}</div>
);
export const H1: React.FC<{ children: React.ReactNode; size?: number }> = ({ children, size = 64 }) => (
  <div style={{ fontFamily: FONT.serif, color: T.forest, fontSize: size, fontWeight: 700, lineHeight: 1.25, letterSpacing: -1, marginBottom: 28 }}>{children}</div>
);
export const Foot: React.FC<{ left: string; right?: string }> = ({ left, right }) => (
  <div style={{ position: "absolute", left: 96, right: 96, bottom: 176, display: "flex", justifyContent: "space-between", color: T.muted, fontSize: 20 }}><span>{left}</span><span>{right}</span></div>
);
export const Brand: React.FC = () => (
  <div style={{ position: "absolute", top: 40, right: 96, display: "flex", alignItems: "center", gap: 12, color: T.muted, fontSize: 20 }}>
    <span style={{ width: 10, height: 10, borderRadius: 5, background: T.forest }} />莫捲莫認真 · 新北市 AI 黑客松 · 法制局
  </div>
);
export const CountUp: React.FC<{ from: number; to: number; delay?: number; dur?: number; style?: React.CSSProperties }> = ({ from, to, delay = 0, dur = 40, style }) => {
  const frame = useCurrentFrame();
  const v = Math.round(interpolate(frame, [delay, delay + dur], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  return <span style={{ fontVariantNumeric: "tabular-nums", ...style }}>{v.toLocaleString()}</span>;
};
export const Transition: React.FC<{ durationInFrames: number }> = ({ durationInFrames }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, 10, durationInFrames - 10, durationInFrames], [1, 0, 0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ background: T.paper, opacity: o, pointerEvents: "none" }} />;
};
