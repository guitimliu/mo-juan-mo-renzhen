import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Arch, Case, Close, Demo, demoDuration, Intro, Pain, Pipeline, Result, Trust } from "./scenes";
import { Transition } from "./ui";
import { sceneLen } from "./timeline";

export const SCENES: { name: string; comp: React.FC; len: number }[] = [
  { name: "intro", comp: Intro, len: sceneLen(["01_intro"]) },
  { name: "pain", comp: Pain, len: sceneLen(["02_pain"]) },
  { name: "case", comp: Case, len: sceneLen(["03_case"]) },
  { name: "pipeline", comp: Pipeline, len: sceneLen(["04_pipeline"]) },
  { name: "arch", comp: Arch, len: sceneLen(["05_arch"]) },
  { name: "demo", comp: Demo, len: demoDuration },
  { name: "result", comp: Result, len: sceneLen(["09_result"]) },
  { name: "trust", comp: Trust, len: sceneLen(["10_trust"]) },
  { name: "close", comp: Close, len: sceneLen(["11_close"], 1.5) },
];
export const totalFrames = SCENES.reduce((a, s) => a + s.len, 0);

export const Main: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill>
      {SCENES.map((s) => { const f = from; from += s.len; const C = s.comp; return (
        <Sequence key={s.name} from={f} durationInFrames={s.len} name={s.name}><C /><Transition durationInFrames={s.len} /></Sequence>); })}
    </AbsoluteFill>
  );
};
