import React from "react";
import { Composition, registerRoot } from "remotion";
import { Main, totalFrames } from "./Main";
import { Demo, demoDuration } from "./scenes";
import { FPS, H, W } from "./theme";

const Root: React.FC = () => (
  <>
    <Composition id="Main" component={Main} durationInFrames={totalFrames} fps={FPS} width={W} height={H} />
    <Composition id="Demo" component={Demo} durationInFrames={demoDuration} fps={FPS} width={W} height={H} />
  </>
);
registerRoot(Root);
