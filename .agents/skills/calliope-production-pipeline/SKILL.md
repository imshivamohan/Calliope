---
name: calliope-production-pipeline
description: >-
  Comprehensive guide, architectural blueprints, features, operational runbook, and pros/cons
  for Calliope's production audio-video pipeline: dual ComfyUI instances (Visual 8188 / Audio 8189),
  Higgs Audio v3 voice cloning, screenplay dialogue parsing, ShotBrief pre-video audio player,
  single-click visual prompt copying, media-type guarded clipboard pasting, audio header sanitization,
  and automatic video-audio muxing.
---

# Calliope Production Audio-Video Pipeline

This skill provides complete operational, architectural, and troubleshooting knowledge for Calliope's production pipeline spanning visual diffusion, speech/dialogue synthesis, automated shot coverage, and final film assembly.

---

## 1. System Architecture & Topology

Calliope uses a **Dual-ComfyUI Instance Architecture** to eliminate VRAM conflicts between large visual diffusion models (e.g., MiniMax H3, Wan 2.2, Krea 2) and high-parameter neural audio models (e.g., Higgs Audio v3 4B):

```
                                  +---> ComfyUI Visual (:8188) [MiniMax H3 / Wan 2.2 / Krea 2]
                                  |     - RTX 5090 (34.2 GB VRAM)
[Browser UI: :5173]               |     - Handles text2img, character sheets, shot videos
       |                          |
       v                          |
[Calliope Backend (:8247)] -------+---> ComfyUI Audio (:8189) [Higgs Audio v3 / Whisper]
(FastAPI + SQLite WAL)            |     - Dedicated Python environment
                                  |     - Voice cloning, speech synthesis, soundscapes
                                  |
                                  +---> Local LLM / Cloud API
                                        - Story outlining, screenplay, H3 prompt rewrite
```

### Server Endpoints & Ports
* **Calliope Web UI**: `http://127.0.0.1:5173` (SvelteKit 2 + Svelte 5)
* **Calliope Backend**: `http://127.0.0.1:8247` (FastAPI + SQLite WAL)
* **ComfyUI Visual**: `http://127.0.0.1:8188` (`D:\Backups\ComfyUI_test\ComfyUI`)
* **ComfyUI Audio**: `http://127.0.0.1:8189` (`D:\Backups\ComfyUI_AD\ComfyUI`)

### Intelligent Job Routing
In `calliope-backend/src/calliope/queue/worker.py`:
* Any job with `kind in ("audio", "voice", "speech", "tts", "music")` or `payload["audio_endpoint"] = True` is dispatched to `config.settings.comfyui_audio_base_url` (`:8189`).
* All visual jobs (`image`, `video`) route to `config.settings.comfyui_base_url` (`:8188`).
* If `:8189` is temporarily unreachable, the worker automatically logs a warning and falls back to `:8188`.

---

## 2. Audio & Dialogue Synthesis Pipeline (Higgs Audio v3)

### Core Engine
Located in `calliope-backend/src/calliope/audio/higgs.py`:
* **Model**: Higgs Audio v3 (`HiggsV3Generate`, 4B foundation model) with `HiggsV3LoadModel`.
* **Voice Cloning**: Whisper-large-v3-turbo reference audio transcriber (`HiggsV3TranscribeAudio`).
* **Presets**:
  * **Default Female**: `WomanVoice6Sec.mp3`
  * **Default Male**: `ManVoice42Sec.mp3` (re-encoded with clean MP3 headers)
  * **Reference Voice**: Character turnaround reference sample (`c.voice_sample_path`).

### Screenplay Parsing & Cue Grouping
To solve the bug where ComfyUI read `"[1]"` as the spoken word *"one"* or read parenthetical cues like `"(wistful)"` as speech:
* `parse_screenplay_dialogue()` groups multi-line screenplay text into structured character speech turns:
  ```text
  CHARACTER NAME
  (parenthetical cue)
  Actual dialogue spoken by character.
  ```
* `extract_clip_dialogue_turns()` resolves `clip.dialog_lines_covered` directly to speech text, stripping raw line numbers.
* `enhance_for_higgs()` converts cues to Higgs control tags:
  * `(whispering)` -> `<|style:whispering|>`
  * `(laughing)` -> `<|sfx:laughter|>Haha, `
  * `(sighs)` -> `<|sfx:sigh|>`
  * Injects `<|prosody:expressive_high|>` and `<|prosody:pause|>`.

### Dialogue Duration Estimation
In `calliope-backend/src/calliope/agent/coverage_agent.py`:
* `_estimate_dialog_duration()` calculates expected spoken audio length based on words-per-minute (~2.5 words/second + pause punctuation).
* `_normalize_clips()` ensures clip `duration_sec` accommodates the dialogue duration so video doesn't end before the character finishes speaking.

---

## 3. UI Ergonomics & User Controls

### ShotBrief Panel (`ShotBrief.svelte`)
* **Single "Copy Prompt" Button**: Copies **only the visual action description** (`body`), stripping out dialogue lines, scene numbers, and speaker tags.
* **Pre-Video Audio Player**: Prominent inline `<audio controls>` player directly above video generation controls.
* **Voice Regeneration Controls**:
  * Dropdown selector: **Reference Voice**, **Default Female**, **Default Male**.
  * **Expressive Tags** checkbox (toggles Higgs prosody and style cues).
  * **Regenerate Voice** button to re-roll dialogue if performance is unsatisfactory.

### OmniComposer (`OmniComposer.svelte` & `MediaTile.svelte`)
* **"Describe Image" Header with Paste**:
  * Dedicated label and Paste button above the prompt textarea. Reads clipboard via `navigator.clipboard.readText()` with visual confirmation.
* **"Reference Inputs" Section with Paste**:
  * Each media tile has a `.tile-paste` button supporting clipboard image blobs (`navigator.clipboard.read()`) and text paths.
* **Strict Media-Type Enforcement**:
  * Image tiles (`kind: 'image'`) strictly reject `.mp3`, `.wav`, `.m4a`, etc., with a toast error: *"This input requires an image reference, not audio."*
  * Prevents accidental insertion of audio paths into `LoadImage` nodes.

---

## 4. Video & Audio Muxing Integration

### MiniMax H3 Workflows (Workflows 14–20)
* MiniMax H3 Reference-to-Video uses `Ref 1` (Node 148, `LoadImage`) and `Ref 2` (Node 149, `LoadImage`) for **visual character turnaround sheets** and **environment backgrounds**.
* It generates video latents and internal atmospheric soundscapes via `MiniMaxH3SigmaShift` and `VAEDecodeAudio`.

### Instant Clip Audio Muxing (`worker.py`)
* When ComfyUI finishes rendering a video clip, `worker._apply_outputs_to_entities()` checks if the clip has a synthesized `clips.audio_path`.
* If dialogue audio exists, Calliope automatically executes a background FFmpeg pass:
  ```bash
  ffmpeg -y -i <video.mp4> -i <dialogue.mp3> -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest <muxed.mp4>
  ```
* The video file in the Queue and ShotBrief immediately plays with the spoken character voice.

### Master Film Assembly (`export/runner.py`)
* Probes all rendered clips with `ffprobe` for frame rates and audio tracks.
* Resolves `majority-fps` to prevent frame judder.
* Stitches video clips with `xfade` (0.5s crossfades) and layers synthesized dialogue tracks (`audio_path`) with EBU R128 loudness normalization.

---

## 5. Audio & Media Hardening Runbook

### Resolving `[mp3float] Header missing` (PyAV Crash)
* **Root Cause**: ID3 tags, prepended junk bytes, or non-standard frame headers cause PyAV in ComfyUI's `LoadAudio` to fail.
* **Automated Fix**: `ensure_clean_audio()` in `calliope-backend/src/calliope/audio/higgs.py` checks files with `ffmpeg -v error` and automatically re-encodes corrupt files:
  ```bash
  ffmpeg -y -i input.mp3 -c:a libmp3lame -b:a 128k clean.mp3
  ```
* **CLI Quick Fix**:
  ```bash
  python -c "import subprocess; subprocess.run(['ffmpeg', '-y', '-i', 'bad.mp3', '-c:a', 'libmp3lame', '-b:a', '128k', 'fixed.mp3'])"
  ```

### Resolving `No video stream found in file '...mp3'` (LoadImage Crash)
* **Root Cause**: An audio file path was passed to a `LoadImage` node in ComfyUI.
* **Automated Safeguards**:
  * Frontend: `MediaTile.svelte` rejects audio extensions on paste.
  * Backend: `client.py` (`prepare_media_inputs`) and `video_agent.py` strip audio file extensions before queuing.
  * DB Cleanup: Cleans stale audio paths from `video_settings_json`.

---

## 6. Pros & Cons Architectural Analysis

| Architectural Decision | Pros (Advantages) | Cons (Trade-offs) |
|---|---|---|
| **Dual ComfyUI Setup (:8188 Visual / :8189 Audio)** | - Prevents 34GB VRAM thrashing between DiT video and 4B audio models.<br>- Zero model unloading/reloading delays.<br>- Isolated dependency trees. | - Requires maintaining two ComfyUI folders.<br>- Requires running two background terminal tasks. |
| **Higgs Audio v3 (Voice Cloning + Whisper)** | - High natural prosody, breathing, and emotion.<br>- One-shot character voice matching from short sample.<br>- Expressive cue tags (`whispering`, `laughter`). | - Generation takes 3–8s per line.<br>- Sensitive to corrupt MP3 header frames (mitigated via `ensure_clean_audio`). |
| **Post-Render FFmpeg Muxing** | - Works with ANY video model (MiniMax, Wan, LTX, Krea).<br>- Independent video and audio iteration.<br>- Clip preview in UI instantly has voice. | - Lip-sync is not anatomically generated by the diffusion DiT (requires separate lip-sync node if strict mouth matching needed). |
| **Dedicated "Describe Image" & "Reference Inputs" Paste** | - Fast, frictionless workflow from ShotBrief.<br>- Strict type validation prevents ComfyUI crashes.<br>- Visual checkmark feedback. | - Browser clipboard permission prompt may appear on first use. |
| **Coverage Agent Duration Sizing** | - Eliminates video truncation before dialogue ends.<br>- Consistent pacing across dramatic scenes. | - Clips with long monologues are split or extended, taking longer to render. |

---

## 7. Quick Diagnostic Commands

```bash
# Check backend health and project count
python -c "import urllib.request, json; print('Projects:', len(json.loads(urllib.request.urlopen('http://127.0.0.1:8247/api/projects').read().decode())))"

# Check ComfyUI Visual (:8188)
python -c "import urllib.request; print('Visual ComfyUI:', urllib.request.urlopen('http://127.0.0.1:8188/system_stats').status)"

# Check ComfyUI Audio (:8189)
python -c "import urllib.request; print('Audio ComfyUI:', urllib.request.urlopen('http://127.0.0.1:8189/system_stats').status)"

# Run Frontend SvelteKit diagnostic
cd calliope-web && npx svelte-check --tsconfig ./tsconfig.json

# Test clean audio verification
python -c "from calliope.audio.higgs import resolve_audio_path; print(resolve_audio_path('ManVoice42Sec.mp3'))"
```
