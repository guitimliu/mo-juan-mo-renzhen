import React from "react";
import { Composition, registerRoot } from "remotion";
import { Main, totalFrames } from "./Main";
import { FPS, H, W } from "./theme";

const Root: React.FC = () => (
  <Composition id="Main" component={Main} durationInFrames={totalFrames} fps={FPS} width={W} height={H} />
);
registerRoot(Root);
