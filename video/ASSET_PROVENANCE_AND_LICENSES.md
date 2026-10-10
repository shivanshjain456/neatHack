# Asset Provenance & Licensing Manifest — VeriFix Demo Video

Every visual, audio, font, and code artifact used to produce `/home/user/verifix/video/out/verifix_neathack_2026_demo.mp4` is 100% original, captured directly from our live running **VeriFix** application and partner telemetry, or licensed under permissive open-source licenses (`Apache-2.0`, `MIT`, `SIL OFL 1.1`). Zero restricted, watermarked, or unlicensed third-party stock assets are used.

| Asset Path | Category | Provenance / Source | License / Rights |
|---|---|---|---|
| `public/audio/scene_01_hook.mp3` .. `scene_06_oss_and_close.mp3` | Spoken Voiceover (`voice-00`) | Synthesized specifically for this project via registered narrator voice `voice-00` (selected by user Shivansh Jain) | Original project narration — clear for public hackathon submission & social sharing |
| `public/audio/master_track_170s.wav` | Mastered Audio Track (`-15.1 LUFS`) | Mixed by `scripts/build_master_audio.py` combining `voice-00` narration + pure FFmpeg `aevalsrc` mathematical sine-wave ambient pad & transition chimes | 100% procedural math synthesis + original voiceover (zero third-party music samples) |
| `hyperframes-scene/index.html` & `public/captures/hyperframes_caller_trap_intro.mp4` | Authored Motion Scene (`0:00 – 0:08`) | Authored in HTML/CSS + GSAP and deterministically rendered at `1920x1080@30fps` using **HyperFrames `v0.8.145`** (`heygen-com/hyperframes`) | Original project code; HyperFrames CLI is Apache-2.0 |
| `public/captures/01_tab1_run3061_recovery.png` .. `07_tab5_oss_bug_hunt_and_selftest.png` | Live Product UI Captures (`1920x1080`) | Captured directly from the running `VeriFix Mission Control` FastAPI server (`http://127.0.0.1:8000`) via headless Chromium (`scripts/capture_live_ui.mjs`) | 100% original live product footage (`Team HyperX`) |
| `public/screenshots/01_neatlogs_error_and_detection_analysis.png` .. `04_neatlogs_arc_patterns_sankey.png` | Partner Telemetry Proof | Authentic production screenshots from `app.neatlogs.com/analytics` (`projectId=00201e50-a8c9-42cf-84bf-116568a49cd5`) | Original project telemetry (`Team HyperX`) |
| `public/screenshots/verifix_architecture_proof_loop.png` | Architecture Diagram | Generated from `docs/verifix_architecture_proof_loop.svg` in `/home/user/verifix` | 100% original project diagram (`Team HyperX`) |
| `src/index.ts`, `src/Root.tsx`, `src/VeriFixDemo.tsx` | Master Video Composition | Authored React/TypeScript composition rendered via **Remotion `v4.0.534`** (`@remotion/bundler` + `@remotion/renderer`) | Original project code |
| `Inter` & `JetBrains Mono` Fonts | Typography | Installed via Debian `fonts-inter` and `fonts-jetbrains-mono` packages | SIL Open Font License 1.1 (`OFL-1.1`) |
