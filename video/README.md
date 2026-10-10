# VeriFix — Reproducible Demo Video Pipeline (Remotion v4.0.534 + HyperFrames v0.8.145)

This directory (`/home/user/verifix/video`) contains the complete, self-contained, reproducible source and rendered deliverables for the **VeriFix neatHack 2026 Demo Video** (`Team HyperX — Shivansh Jain`).

It is cleanly isolated from the core Python package (`/home/user/verifix/src/verifix`) so that video rendering dependencies never alter core agent runtime behavior.

---

## 1. Delivered Files

- **Final Playable MP4 (`1920x1080`, `16:9`, `30.00 fps`, `H.264` + `AAC`, `170.00s` / `2:50.00`, `11.69 MB`)**:
  - `/home/user/verifix/video/out/verifix_neathack_2026_demo.mp4`
  - `/home/user/verifix/verifix_neathack_2026_demo.mp4` (convenience copy at repository root)
- **Synchronized Captions (`.srt`, `.vtt`, and frame-indexed `.json`)**:
  - `/home/user/verifix/video/out/verifix_neathack_2026_demo.srt`
  - `/home/user/verifix/video/out/verifix_neathack_2026_demo.vtt`
  - `/home/user/verifix/video/src/captions.json`
- **Visual QA Contact Sheet & Machine-Readable Verification Report**:
  - `/home/user/verifix/video/out/qa_contact_sheet.png` (12 timestamped beat frames extracted from the final MP4)
  - `/home/user/verifix/video/out/video_qa_report.json`
- **Editable Source Code**:
  - **Remotion (`v4.0.534`) Master Composition**: `src/index.ts`, `src/Root.tsx`, `src/VeriFixDemo.tsx`, `scripts/render_master_video.mjs`
  - **HyperFrames (`v0.8.145`) Authored Motion Scene (`0:00 – 0:08`)**: `hyperframes-scene/index.html` → `public/captures/hyperframes_caller_trap_intro.mp4`
  - **Live Product UI Capture Script**: `scripts/capture_live_ui.mjs`
  - **Procedural Sound Engine & Voiceover Mixer (`voice-00`)**: `scripts/build_master_audio.py`
  - **Creative Brief, Claim-to-Evidence Map & Script**: `STORYBOARD_AND_SCRIPT.md`
  - **Asset Provenance & Licensing Manifest**: `ASSET_PROVENANCE_AND_LICENSES.md`

---

## 2. How to Reproduce End-to-End

Ensure the `VeriFix Mission Control` server is running on `http://127.0.0.1:8000` (`python3 -m verifix.cli serve --host 0.0.0.0 --port 8000`), then from `/home/user/verifix/video`:

```bash
# 1. Install dependencies (Node.js >= 22, FFmpeg, Chromium)
npm install

# 2. Capture fresh 1920x1080 live product screenshots across all 5 Mission Control tabs
npm run capture

# 3. Lint and render the authored HyperFrames v0.8.145 motion scene (0:00 - 0:08)
TMPDIR=/home/user/.tmp_render CHROME_PATH=/usr/bin/chromium npx hyperframes lint hyperframes-scene
TMPDIR=/home/user/.tmp_render CHROME_PATH=/usr/bin/chromium npx hyperframes render hyperframes-scene \
  -o public/captures/hyperframes_caller_trap_intro.mp4 --fps 30 --low-memory-mode

# 4. Build the 170.0s mastered stereo audio track (-15.1 LUFS) and synchronized .srt/.vtt captions
npm run sfx

# 5. Render the master 1920x1080@30fps H.264 + AAC MP4 via @remotion/bundler + @remotion/renderer
TMPDIR=/home/user/.tmp_render node scripts/render_master_video.mjs

# 6. Run automated ffprobe, EBU R128 loudness, black-frame detection & 12-beat contact sheet QA
npm run qa
```

---

## 3. Verification Summary (`out/video_qa_report.json`)

- **Container & Codecs**: MP4 (`+faststart`), Video: `h264 (High@L4.0, yuv420p, 1920x1080, SAR 1:1, DAR 16:9, 30/1 fps)`, Audio: `aac (48000 Hz, 2 channels, 192 kbps)`
- **Total Duration**: **`170.00 seconds` (`2:50.00`)** — `10.00 seconds` under the `180.0s` (`3:00`) hard ceiling
- **Loudness & Peak**: Integrated Loudness **`-15.1 LUFS`**, True Peak **`-1.4 dBFS`**
- **Black Frames Detected**: **`0`** (`black_frame_events: []`)
