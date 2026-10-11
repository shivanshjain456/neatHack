import React from "react";
import { Composition } from "remotion";
import { FULL_FRAMES, FullVideo } from "./FullVideo";
import { HIGHLIGHT_FRAMES, HighlightVideo } from "./HighlightVideo";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="VeriFixFull" component={FullVideo} fps={30} width={1920} height={1080} durationInFrames={FULL_FRAMES} />
    <Composition id="VeriFixHighlight" component={HighlightVideo} fps={30} width={1920} height={1080} durationInFrames={HIGHLIGHT_FRAMES} />
  </>
);
