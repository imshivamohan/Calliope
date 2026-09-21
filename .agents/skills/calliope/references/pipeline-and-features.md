# Calliope Pipeline & Features Guide

Calliope guides creative projects through four sequential pipeline stages — **Story**, **Assets**, **Script**, and **Video** — culminating in the final stitched **Film View**.

```
  +--------------+     +---------------+     +--------------+     +---------------+     +-------------+
  | 1. Story     | --> | 2. Assets     | --> | 3. Script    | --> | 4. Video      | --> | 5. Film     |
  | Beats, Cast, |     | Visual Refs,  |     | Screenplay & |     | Per-Clip Gen, |     | Crossfades, |
  | Environments |     | Turnarounds   |     | Shot Coverage|     | Video Extend  |     | Master MP4  |
  +--------------+     +---------------+     +--------------+     +---------------+     +-------------+
```

---

## 1. Stage 1: Story Stage

The Story stage turns a raw prompt or logline into structured narrative material.

### Capabilities
- **Project Setup**: Define Title, Idea/Premise, Genre, Tone, and Target Duration (e.g. 30s, 1m, 2m, 5m). Genre and Tone map cleanly through `formOptions.ts` for localization.
- **Draft Storyline**:
  - Clicking **Draft Storyline** triggers `POST /api/projects/{id}/generate-story` or opens a linked agent session in the Agents view.
  - Generates:
    - **Story Beats**: Sequential narrative milestones (`order_index`, `title`, `description`).
    - **Characters**: Core cast with `name`, `role`, `age`, `appearance`, `personality`, and visual `consistency_prompt`.
    - **Locations**: Settings with `name`, `description`, and `consistency_prompt`.
    - **Items / Props**: Key plot items and objects with `name` and `description`.
- **Chunked Generation & Repeat Guards**:
  - Large storylines generate in structured batches with anti-repetition guards preventing cyclical text generation.
- **Manual Editing**: Full in-place editing, addition, reordering, and deletion of beats, characters, locations, and items.

---

## 2. Stage 2: Assets Stage

Before filming, characters, locations, and props need visual identity references.

### Capabilities
- **Reference Image Generation**:
  - Uses ComfyUI image workflows (e.g., SDXL, Flux, Krea2, custom checkpoints).
  - Configurable shared parameters: Width, Height, Sampling Steps, CFG Scale, Seed.
- **Entity Consistency**:
  - Characters can generate **Portraits** (facial close-up) and **Sheets** (3-angle turnaround / expression sheet).
  - Stored consistency prompts guarantee aesthetic continuity across scenes.
- **Isolated Regeneration**:
  - Generate or re-roll any character, location, or item individually without touching others.
- **External Asset Ingestion**:
  - Attach images directly from the **Playground**, **Asset Library**, or **3D Build Scene** viewport captures.

---

## 3. Stage 3: Script & Shot Coverage Pass

A conventional LLM scene output is usually a block of prose. Calliope splits this stage into two critical phases: **Screenplay Generation** and **Shot Coverage (Scene -> Clips)**.

### Phase A: Screenplay Generation
- `POST /api/projects/{id}/generate-script` writes screenplay-standard scenes.
- Each scene retains:
  - **Slugline / Heading**: e.g., `INT. CYBERPUNK LAB - NIGHT`.
  - **Action Prose**: Descriptive blocking and scene activity.
  - **Verbatim Dialogue**: Full character lines (e.g., `KAI: We're out of time.`).
  - **Estimated Duration**: Seconds required to play the scene.
  - **Character & Location Links**: Linked directly to entities from the Story stage.

### Phase B: Shot Coverage Pass (Scene → Clips)
Generating an entire 2-minute scene as a single AI video prompt produces hallucinations and audio drift. Calliope's coverage pass breaks each scene into shot clips:
- Triggered per scene (`POST /api/projects/{id}/scenes/{scene_id}/expand-clips`) or project-wide (`POST /api/projects/{id}/expand-clips`).
- Splits the scene into ~5–10 second cinematic takes (`#1.1`, `#1.2`, `#1.3`, ...).
- **Allocates Dialogue Verbatim**: Maps specific dialogue lines to each clip using 1-based indexing (`dialog_lines_covered`). A clip only performs its allocated lines.
- **Assigns Shot Sizes**:
  - `CU`: Close-Up
  - `MCU`: Medium Close-Up
  - `MS`: Medium Shot
  - `WS`: Wide Shot
  - `OTS`: Over-The-Shoulder
  - `POV`: Point of View
  - `ECU`: Extreme Close-Up

---

## 4. Stage 4: Video Generation Stage

Clips are rendered by driving ComfyUI video models (e.g. MiniMax H3, CogVideoX, Wan2.1, HunyuanVideo).

### Two-Column Studio Layout
- **Left Column**: High-resolution video player, interactive timeline filmstrip with clip thumbnails, and collapsible scene screenplay drawer.
- **Right Column**: Generation inspector with workflow selector, dynamic inputs, prompt preview, and render history.

### Shot Brief Panel
At the top of the Video stage, the selected clip displays its exact coverage brief:
- Shot label (`#Scene.Clip`, e.g. `#2.1`)
- Shot size and target duration
- Action description and assigned dialogue lines
- Characters present in the shot
- **Copy Button**: Transfers the brief text to clipboard for prompt editing.

### Prompt Review Gate & Draft System
Generate never executes blind:
1. Clicking **Generate** opens the **Prompt Preview Modal**.
2. Displays the exact payload destined for ComfyUI's `(Input:prompt)` node.
3. Supports **MiniMax H3 6-Section Profile** (formatted automatically by LLM) or **Plain Prose**.
4. **Interactive Controls**:
   - **Inline Edit**: Adjust camera motion notes, lighting, or pacing before queuing.
   - **Regenerate**: Ask the LLM for an alternative prompt take.
   - **Save Draft**: Saves the customized prompt to `video_settings_json`. Batch **Generate All** honors saved drafts without calling the LLM again.
   - **Cancel**: Aborts with nothing queued.

### Continue From Previous Clip (Video Extend)
For continuous long takes without hard cuts:
- Enable the **Continue from previous clip** toggle (`chain_from_prev = 1`).
- Requires a workflow with a `(Input:video)` node (`LoadVideo`).
- **Clip Source Picker**:
  - `Auto`: Resolves the previous rendered clip in timeline order dynamically when the job runs (safe even during batch queuing because jobs execute sequentially).
  - `Upload File`: Extend from an uploaded video file (from Playground).
  - `From Timeline`: Explicitly select any earlier rendered clip.
- **Tuned Model Parameters** (e.g. MiniMax H3 Extend):
  - `context_frames`: 2
  - `ref_spacing`: 1–2
  - `ref_decay`: 0.3
  - `ref_ramp`: 3–4 (5–6 for high motion)

### Render History & Job Inspect
- Clicking **View prompt & inputs** opens the scene's past render history.
- Each job displays as a chip with status, output paths, and exact JSON payload submitted to ComfyUI.
- **Copy settings to form**: Restores an older job's parameters back into the active inspector form.

---

## 5. Stage 5: Film View & Master Export

When all shot clips are rendered, Calliope stitches them into a release-ready film.

### Capabilities
- **Majority-FPS Conformance**:
  - Probes every clip using `ffprobe`.
  - Determines the majority frame rate (e.g., 24 fps, 25 fps, 30 fps).
  - Projects conform to the majority rate, preventing judder caused by arbitrary fixed interpolation.
- **0.5s Video & Audio Crossfades**:
  - Joins adjacent clips using smooth FFmpeg `xfade` (video) and `acrossfade` (audio) transitions.
- **Audio Loudness Normalization**:
  - Applies EBU R128 two-pass loudness filters to normalize speech and sound effects across varying generation runs.
- **Master Resolution**: Conforms all clips to 1080p (1920x1080) H.264 MP4.
- **Completion State**: Automatically updates the project status to `'completed'`.
