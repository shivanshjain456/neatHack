import path from "path";
import fs from "fs";
import { execFileSync } from "child_process";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition, openBrowser } from "@remotion/renderer";

const VIDEO_DIR = "/home/user/verifix/video";
const TMP_DIR = "/home/user/.tmp_render/segments";
const OUT_MP4 = path.join(VIDEO_DIR, "out", "verifix_neathack_2026_demo.mp4");
const CAPTIONS_PATH = path.join(VIDEO_DIR, "src", "captions.json");
const MASTER_WAV = path.join(VIDEO_DIR, "public", "audio", "master_track_170s.wav");
const HYPERFRAMES_MP4 = path.join(VIDEO_DIR, "public", "captures", "hyperframes_caller_trap_intro.mp4");

fs.mkdirSync(TMP_DIR, { recursive: true });
fs.mkdirSync(path.dirname(OUT_MP4), { recursive: true });

// Visual scene beats from src/VeriFixDemo.tsx (in seconds)
// Scene 1A (0..8s) is the authored HyperFrames v0.8.145 video (`hyperframes_caller_trap_intro.mp4`).
// From 8.0s..170.0s, we slice the timeline at every union of scene boundaries and caption boundaries
// so every caption change and every visual scene transition is frame-accurate at 30 fps.
const SCENE_BOUNDARIES = [8.0, 28.0, 43.0, 57.5, 71.5, 85.0, 101.0, 116.5, 143.0, 161.0, 170.0];

async function main() {
  console.log("[1/4] Bundling Remotion master composition (src/index.ts -> VeriFixDemo)...");
  const serveUrl = await bundle({
    entryPoint: path.join(VIDEO_DIR, "src", "index.ts"),
    publicDir: path.join(VIDEO_DIR, "public"),
  });

  const browser = await openBrowser("chrome", {
    browserExecutable: "/usr/bin/chromium",
  });

  const composition = await selectComposition({
    serveUrl,
    id: "VeriFixDemo",
    puppeteerInstance: browser,
  });

  const captions = JSON.parse(fs.readFileSync(CAPTIONS_PATH, "utf-8"));

  // Collect all cut points in [8.0, 170.0]
  const cutPointsSet = new Set(SCENE_BOUNDARIES);
  for (const c of captions) {
    if (c.start_sec > 8.0 && c.start_sec < 170.0) cutPointsSet.add(Number(c.start_sec.toFixed(2)));
    if (c.end_sec > 8.0 && c.end_sec < 170.0) cutPointsSet.add(Number(c.end_sec.toFixed(2)));
  }
  const cuts = Array.from(cutPointsSet).sort((a, b) => a - b);

  const intervals = [];
  for (let i = 0; i < cuts.length - 1; i++) {
    const startSec = cuts[i];
    const endSec = cuts[i + 1];
    if (endSec - startSec >= 0.04) {
      intervals.push({ startSec, endSec, durationSec: Number((endSec - startSec).toFixed(4)) });
    }
  }

  console.log(`[2/4] Rendering ${intervals.length} Remotion intervals across 8.0s..170.0s via @remotion/renderer...`);

  const segmentFiles = [];

  // Segment 0 (0.0s -> 8.0s): Authored HyperFrames v0.8.145 video with burned-in SRT subtitles for 0..8s
  const seg0Path = path.join(TMP_DIR, "seg_000_hyperframes.mp4");
  const srtPath = path.join(VIDEO_DIR, "out", "verifix_neathack_2026_demo.srt");
  execFileSync("ffmpeg", [
    "-y",
    "-i",
    HYPERFRAMES_MP4,
    "-vf",
    `subtitles=${srtPath}:force_style='FontName=Inter,FontSize=13,PrimaryColour=&H00FAFAFA,BackColour=&Hcc140A06,BorderStyle=4,Outline=1,Shadow=0,MarginV=10'`,
    "-r",
    "30",
    "-c:v",
    "libx264",
    "-preset",
    "veryfast",
    "-crf",
    "18",
    "-pix_fmt",
    "yuv420p",
    "-an",
    seg0Path,
  ]);
  segmentFiles.push(seg0Path);

  for (let idx = 0; idx < intervals.length; idx++) {
    const iv = intervals[idx];
    const midSec = (iv.startSec + iv.endSec) / 2.0;
    // Pick a frame well past the 12-frame spring entrance so the card is fully settled
    const sampleFrame = Math.min(5099, Math.max(240, Math.round(midSec * 30)));
    const pngPath = path.join(TMP_DIR, `still_${String(idx + 1).padStart(3, "0")}.png`);
    const mp4Path = path.join(TMP_DIR, `seg_${String(idx + 1).padStart(3, "0")}.mp4`);

    await renderStill({
      composition,
      serveUrl,
      output: pngPath,
      frame: sampleFrame,
      puppeteerInstance: browser,
      imageFormat: "png",
    });

    execFileSync("ffmpeg", [
      "-y",
      "-loop",
      "1",
      "-t",
      String(iv.durationSec),
      "-r",
      "30",
      "-i",
      pngPath,
      "-vf",
      "fade=t=in:st=0:d=0.12",
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-crf",
      "18",
      "-pix_fmt",
      "yuv420p",
      "-an",
      mp4Path,
    ]);
    segmentFiles.push(mp4Path);
    if ((idx + 1) % 6 === 0 || idx === intervals.length - 1) {
      console.log(`  Rendered ${idx + 1}/${intervals.length} Remotion segments (t=${iv.endSec.toFixed(1)}s)`);
    }
  }

  await browser.close({ silent: true });

  console.log("[3/4] Concatenating HyperFrames + Remotion video segments and muxing mastered voice-00 audio...");
  const concatListPath = path.join(TMP_DIR, "concat_list.txt");
  const concatContent = segmentFiles.map((f) => `file '${f}'`).join("\n");
  fs.writeFileSync(concatListPath, concatContent, "utf-8");

  execFileSync("ffmpeg", [
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    concatListPath,
    "-i",
    MASTER_WAV,
    "-map",
    "0:v:0",
    "-map",
    "1:a:0",
    "-c:v",
    "libx264",
    "-preset",
    "veryfast",
    "-crf",
    "18",
    "-pix_fmt",
    "yuv420p",
    "-r",
    "30",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-ar",
    "48000",
    "-ac",
    "2",
    "-movflags",
    "+faststart",
    "-t",
    "170.0",
    OUT_MP4,
  ]);

  // Also copy to /home/user/verifix/verifix_neathack_2026_demo.mp4 for top-level convenience
  const rootCopy = "/home/user/verifix/verifix_neathack_2026_demo.mp4";
  fs.copyFileSync(OUT_MP4, rootCopy);
  console.log(`[4/4] Done! Master MP4 written to ${OUT_MP4} and ${rootCopy}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
