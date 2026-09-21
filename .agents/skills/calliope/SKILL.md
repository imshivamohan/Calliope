---
name: calliope
description: >-
  Comprehensive operational and architectural guide for Calliope, the local-first story-to-video studio.
  Use this skill whenever building, testing, debugging, configuring, or extending Calliope
  (FastAPI backend, SvelteKit frontend, ComfyUI workflows, 3D Build Scene, AI Canvas, video export, multi-agent harness, queue worker, or SQLite database).
---

# Calliope: Local-First Story-to-Video Studio

Calliope is a local-first creative suite that transforms story ideas into fully stitched cinematic films. Everything runs locally on the user's machine: projects live in SQLite, generated media lives in local directories, and generation is driven by the user's own ComfyUI instance with local or hosted LLMs.

---

## 1. Quick Commands & Runbook

### Environment Prerequisites
- **Python 3.11+** with virtual environment
- **Node.js 18+** with npm
- **FFmpeg & FFprobe** on system PATH (essential for film stitching, majority-FPS analysis, and Build Scene MP4 normalization)
- **Running ComfyUI** instance (HTTP API default: `http://127.0.0.1:8188`)
- **OpenAI-compatible LLM endpoint** (Ollama, LM Studio, vLLM, or hosted API)

### Start Services
```bash
# Diagnostic check
.agents/skills/calliope/scripts/check-health.py

# Run Backend (FastAPI on http://127.0.0.1:8247)
cd calliope-backend
.venv/bin/python -m calliope.main --host 127.0.0.1 --port 8247

# Run Frontend (SvelteKit on http://127.0.0.1:5173, proxies /api -> 8247)
cd calliope-web
npm run dev

# Or use the unified runner:
.agents/skills/calliope/scripts/dev-run.sh backend
.agents/skills/calliope/scripts/dev-run.sh frontend

# AGY Director CLI (Antigravity-driven story, script, shot breakdown, prompt staging)
.agents/skills/calliope/scripts/director.py list-projects
.agents/skills/calliope/scripts/director.py ingest-package --file package.json

### Run Tests
```bash
# Backend pytest suite (500+ tests)
cd calliope-backend
.venv/bin/pytest -q tests/test_roles.py tests/test_contract_vocabulary.py tests/test_h3_profile.py

# Frontend SSR storage safety test (guard for Node 22+)
cd calliope-web
npm test

# Frontend TypeScript check
cd calliope-web
npm run check
```

---

## 2. System Architecture & Topology

Calliope is organized into a clean dual-tier architecture:

```
[Browser Client] <--- SSE (/api/events) ---+ [Calliope Backend (FastAPI)]
(SvelteKit 2 + Svelte 5 + Three.js)        |  - REST APIs (projects, story, scenes, etc.)
                                           |  - Multi-Agent Harness & Planner
                                           |  - Queue Worker & ComfyUI HTTP Client
                                           |  - FFmpeg Stitching Engine
                                           |
                                           +---> [SQLite 3 (WAL Mode)]
                                           +---> [ComfyUI (HTTP: prompt/history/view)]
                                           +---> [LLM Endpoints (OpenAI-compatible)]
```

For complete database schema tables (all 19 tables), configuration properties, and SSE event specifications, see:
- [Architecture & Database Schema Reference](./references/architecture-and-schema.md)

---

## 3. End-to-End Feature Matrix & Workflow Guide

### Feature 1: Project & Workspace Management
- **Project Creation**: Initialize projects with Title, Premise, Genre, Tone, and Target Duration.
- **Portability & Path Rebasing**: Calliope re-anchors asset paths on startup if the project folder is moved.
- **Status Progression**: Projects advance from `'draft'` to `'in_progress'` to `'completed'`.

### Feature 2: Stage 1 — Story Drafting & Entity Generation
- **Draft Storyline**: Automatically decomposes the premise into:
  - **Story Beats**: Sequential dramatic outline (`story_beats`).
  - **Characters**: Core cast with role, age, appearance, personality, and visual consistency prompts.
  - **Locations**: Environment settings with descriptive details and visual consistency prompts.
  - **Items**: Key props and narrative objects.
- **Anti-Repetition Guards & Chunking**: Generates content in bounded chunks with repeat guards to prevent looping.
- **Manual Control**: Full inline editing, reordering, creation, and deletion of all entities.

### Feature 3: Stage 2 — Assets & Reference Imagery
- **ComfyUI Reference Generation**: Drives text-to-image workflows to render character portraits, turnaround expression sheets, location backdrops, and item cards.
- **Shared Parameters**: Adjust width, height, sampling steps, CFG, and seed across runs.
- **Isolated Regeneration**: Regenerate any single character or location without touching others.
- **Cross-Surface Ingestion**: Attach images directly from Playground, Asset Library, or 3D Build Scene captures.

### Feature 4: Stage 3 — Script Writing & Shot Coverage Pass
- **Full Screenplay Generation**: Generates standard screenplay scenes with sluglines (`INT./EXT.`), rich action prose, verbatim dialogue lines, and estimated durations.
- **Shot Coverage Pass (Scene → Clips)**:
  - Solves the single-prompt AI video hallucination problem by splitting each scene into ~5–10 second shot clips (`#1.1`, `#1.2`, `#1.3`, ...).
  - **Allocates Dialogue**: Maps exact dialogue lines to each clip (`dialog_lines_covered`) using 1-based indexing.
  - **Assigns Cinematic Shot Sizes**: Close-Up (CU), Medium Close-Up (MCU), Medium Shot (MS), Wide Shot (WS), Over-the-Shoulder (OTS), Point of View (POV).

### Feature 5: Stage 4 — Video Generation Stage
- **Shot Brief Panel**: Top banner displays the selected clip's `#Scene.Clip` label, shot size, duration, action description, performed dialogue, and characters. Includes 1-click clipboard copy.
- **Two-Column Studio Layout**: Player, filmstrip, and screenplay drawer on the left; generation inspector and prompt review on the right.
- **Prompt Review Gate**: Clicking Generate displays exact payload for `(Input:prompt)`. Allows inline editing, LLM regeneration, and saving drafts. Batch **Generate All** honors saved drafts.
- **Continue from Previous Clip (Video Extend)**:
  - Enables long continuous takes without hard cuts using extend-capable models (e.g. MiniMax H3 Extend).
  - Requires workflow node tagged `(Input:video)` (`LoadVideo`).
  - Clip Source Picker: **Auto** (dynamic timeline predecessor), **Upload file**, or **From timeline**.
- **Render History**: "View prompt & inputs" drawer displays past render job chips, payloads, and "Copy settings to form" recall.

### Feature 6: Film View & Master FFmpeg Export
- **Majority-FPS Conformance**: Probes all clips with `ffprobe`; exports at the majority clip frame rate (e.g., 24 fps stays 24 fps), eliminating frame pacing judder.
- **0.5s Crossfades**: Applies smooth video (`xfade`) and audio (`acrossfade`) transitions.
- **EBU R128 Loudness Normalization**: Two-pass audio filter balances dialogue and SFX.
- **Master Assembly**: Conforms all footage to 1080p H.264 MP4 and marks project `'completed'`.

For deep-dive pipeline details, see:
- [Pipeline & Features Guide](./references/pipeline-and-features.md)

---

## 4. Specialized Creative Surfaces

### Feature 7: 3D Build Scene (Shot Composer)
- **Browser-Based 3D Blockout** (`/build-scene`): Three.js viewport acts as the single surface for real-time preview, high-res still captures, and deterministic video timeline export.
- **Staging**: Posable 3D mannequins (`mannequin-js`), joint angle sliders, posture adjustments, pose presets (`list_poses`, `apply_pose`).
- **Framing & Keyframes**: Timeline keyframe tracks for transforms, poses, and camera angles (framing is user-controlled; agent animates objects).
- **Agent Verification Gates**:
  - **Brief Gate**: Agent must call `record_build_scene_gate('brief')` before mutating scene geometry.
  - **Cut Gate**: Agent must call `record_build_scene_gate('cut')` before requesting captures.
- **Server Normalization**: Client MediaRecorder WebM is normalized to H.264 MP4 via FFmpeg.

For Build Scene technical details, see:
- [Build Scene & 3D Shot Composer Reference](./references/build-scene-and-shot-composer.md)

### Feature 8: AI Canvas (`/canvas`)
- **Infinite Spatial Workspace**: Built on `@xyflow/svelte`.
- **Node Types**: `entity` (cast/props), `image`, `video` (with HTML5 player), `text` (script/notes), and `workflow` (executable blocks).
- **Data & Link Edges**: Connect image/entity nodes to workflow inputs with role mapping (`dst_role`).
- **Live Workflow Execution**: Run workflows directly on canvas with live progress indicators.
- **Unique Deduplication Index**: Prevents twin cards when agent tools and frontend auto-materializers race.
- **Auto-Tidy & Honest Deletion**: Cleans layout spacing and deletes nodes/edges directly from the database.

### Feature 9: Free-Form Playground & Asset Library
- **Playground (`/playground`)**: Unconstrained generation surface. Upload custom media (`POST /api/playground/uploads`), run arbitrary workflows, and attach outputs to projects in 1 click (`POST /api/playground/attach`).
- **Asset Library (`/library`)**: Centralized media explorer across all projects and sessions with filtering (projects, entities, uploads, captures), lazy loading, and steering library integration.

For canvas and playground mechanics, see:
- [AI Canvas, Playground & Asset Library Reference](./references/ai-canvas-and-playground.md)

---

## 5. ComfyUI Workflow Engine & Role Contracts

### Pure HTTP Integration
- Calliope communicates with ComfyUI **exclusively via HTTP REST** (`/upload/image`, `/prompt`, `/history`, `/view`). It never touches ComfyUI's local filesystem.

### Node Title Role Tagging Contract
Calliope discovers workflow inputs and outputs by parsing role tags inside node titles:
```text
Node Title (Input:<role>)
Node Title (Output:<role>)
```

#### Canonical Input Roles
`prompt` (`positive`), `negative` (`neg`), `width` (`w`), `height` (`h`), `character` (`char`, `portrait`, `sheet`, `face`, `ref`), `location` (`loc`, `environment`, `env`, `background`, `scene`), `image` (`img`), `video` (`vid`), `audio` (`sound`, `sfx`), `seed`, `duration` (`dur`, `length`, `seconds`).

#### Canonical Output Roles
`image` (`img`), `video` (`vid`).

### Prompt Profiles
- **`minimax_h3_ref`**: Official 6-section reference format (`subject_definitions:`, `summary:`, `retention_analysis:`, `detailed_description:`, `overall_soundscape:`, `non_diegetic_music:`) with `<Subject N>` ordering and `<d>[Lang] ...</d>` dialogue tags for MiniMax H3 / Hailuo 02.
- **`krea2`**: Natural language descriptive prompts for character turnarounds, portrait sheets, environment establishing layouts, and hero props without tag soup.
- **`h3_rewrite_extra_body`**: Settings dictionary to suppress reasoning tokens on thinking models (e.g. `{"chat_template_kwargs": {"enable_thinking": false}}`).
- **`prose`**: Standard descriptive action and dialogue prose.

For workflow details and troubleshooting, see:
- [ComfyUI Workflows & Role Contracts Reference](./references/comfyui-workflows-and-roles.md)

---

## 6. Background Queue & Polling Engine

- **Concurrency Control**: `queue_concurrency` (default 1) executes jobs sequentially or in parallel.
- **Configurable Polling Timeout**: `queue_poll_timeout_sec` (default 1800s / 30m; set to `0` for indefinite polling during long video generations).
- **Error Diagnostics**: Surfaces exact HTTP 400 validation failures and offending node IDs.
- **Clean Cancellation**: Stopping or deleting a job in Calliope actively aborts the prompt on ComfyUI.

---

## 7. Production Multi-Agent System

- **Agent Roles**: Main Agent, Planner, Story Agent, Script Agent, Assets Agent, Video Agent.
- **Model-per-Agent Routing**: Pin different LLM profiles to each role in **Settings → Agent** (`AGENT_LLM_ROLES`).
- **Real-Time Mid-Run Steering**: Send messages while the agent is executing; buffered and ingested safely at step boundaries (`[STEERING]` tag) without invalidating tool call sequences.
- **Interactive Question Cards**: Agent calls `ask_user` with structured options, pausing until the user selects or types.
- **Scoped Memory (`agent_memory`)**: Save, list, or forget memories scoped to `global` or `project`.
- **Operator Hardening Prompt**: Strict prompt-injection resistance, scope enforcement, anti-fabrication rules, and destructive action guards.
- **60+ Tool Registry**: Full database, canvas, 3D blockout, and queue manipulation capabilities.

For agent harness and tool schemas, see:
- [Agent System & Tool Contracts Reference](./references/agent-system-and-contracts.md)

---

## 8. Internationalization (i18n) & UI Architecture

- **7 Supported Languages**: English (`en`), Chinese (`zh`), Spanish (`es`), French (`fr`), German (`de`), Japanese (`ja`), Korean (`ko`).
- **Strict Typing**: All translations are checked against `type Dict = typeof en` (1,000+ keys). Missing keys fail the TypeScript build.
- **SSR Storage Guard**: `lib/storage.ts` probes callable methods, preventing `localStorage.getItem is not a function` crashes under Node 22+.

For localization and component architecture, see:
- [i18n & UI Architecture Reference](./references/i18n-and-ui-system.md)

---

## 9. AGY Director Mode (Zero-Local-LLM Architecture)

When running Calliope without a local LLM or to preserve 100% of GPU/VRAM for ComfyUI diffusion models:
- **Antigravity (AGY CLI / Assistant)** takes 100% ownership of:
  - Story idea & beat outlining
  - Krea 2 optimized character turnaround sheets & visual consistency prompts
  - Krea 2 optimized environment & hero prop reference prompts
  - Full screenplay writing (action lines & verbatim dialogue)
  - Shot coverage expansion (breaking 1 scene into $N$ clips `#N.M`, 1-based dialogue mapping, shot sizing)
  - MiniMax H3 6-section reference video diffusion prompt engineering (`subject_definitions:`, `summary:`, `retention_analysis:`, `detailed_description:`, `overall_soundscape:`, `non_diegetic_music:`)
  - Direct database staging via `.agents/skills/calliope/scripts/director.py`
- **ComfyUI (Local)** handles asset & video diffusion generation without VRAM competition.

For the operational runbook and commands, see:
- [AGY Director Workflow Guide](./references/agy-director-workflow.md)

---

## 10. Common Failure Modes & Troubleshooting

| Issue | Root Cause | Solution |
|---|---|---|
| ComfyUI "doesn't know what to generate" | Workflow node title missing role tag | Ensure prompt node title is `Node Name (Input:prompt)`. |
| ComfyUI fails with 400 validation error | Missing or invalid uploaded reference | Check error detail for offending node ID and verify file path. |
| Video Extend button disabled | Workflow missing `(Input:video)` | Add a `LoadVideo (Input:video)` node to the ComfyUI workflow. |
| Agent turn stalled on render | Long video generation exceeding timeout | Increase `queue_poll_timeout_sec` in Settings or set to `0`. |
| Thinking model slow on H3 prompt rewrite | LLM wasting reasoning tokens on formatting | Set `h3_rewrite_extra_body` in settings to disable thinking. |
| Node 22+ SSR crash on build/run | Direct `localStorage` access without method probing | Ensure all web-storage reads use `safeGetItem()` from `lib/storage.ts`. |
| Stale asset paths after moving folder | Absolute paths in SQLite pointing to old root | Restart backend; `rebase_stale_asset_paths()` automatically fixes paths. |
