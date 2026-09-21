---
name: calliope-director
description: >-
  Autonomous AI Film Director and Showrunner for Calliope projects.
  Use this skill whenever a user provides a Calliope project URL (e.g., http://127.0.0.1:5173/project/<id>),
  a project ID (e.g., "project 4", "project/2"), or asks to generate, write, stage, or flesh out the rest
  of a Calliope story, screenplay, characters, shot coverage, or video prompts.
  Extracts the project premise, crafts dramatic story beats, designs consistent characters, environments,
  and items, authors screenplay scenes, breaks down coverage into shot clips, pre-stages ComfyUI video
  diffusion prompts, and writes everything directly into Calliope's SQLite database.
---

# Calliope Director: Autonomous Story-to-Screenplay Staging

The **Calliope Director** skill allows Antigravity (AGY) to take total creative control over story development, worldbuilding, screenwriting, cinematography, and diffusion prompt staging for any Calliope project.

Local ComfyUI is reserved exclusively for rendering image assets and video clips; all narrative generation, screenplay formatting, and shot engineering is handled autonomously by Antigravity through this skill.

---

## Directing Workflow

When a user shares a Calliope project URL (e.g., `http://127.0.0.1:5173/project/4`) or asks to generate the rest of a project, follow this exact procedure:

```
[User shares URL / ID]
        │
        ▼
[1. Parse Project ID] ──────> Extract <id> (e.g., 4) from http://127.0.0.1:5173/project/4
        │
        ▼
[2. Read Project Premise] ──> Run: .agents/skills/calliope-director/scripts/director.py read <id>
        │
        ▼
[3. Direct & Author] ───────> Write Story Beats, Characters, Locations, Items, Script, Clips, ComfyUI Prompts
        │
        ▼
[4. Ingest into Calliope] ───> Write to temp JSON & Run: director.py ingest <id> --file <pkg.json>
        │
        ▼
[5. Deliver Executive Links]> Output direct links to Story, Assets, Script, and Video stages
```

---

## Step 1: Parse the Project ID

Extract the numerical project ID from the user's message or URL:
- `http://127.0.0.1:5173/project/4` → `4`
- `http://localhost:5173/project/12?stage=video` → `12`
- `project 5` or `project/5` → `5`

---

## Step 2: Read the Project Record

Inspect the existing premise and metadata from Calliope's SQLite database:

```bash
.agents/skills/calliope-director/scripts/director.py read <project_id>
```

This prints the project title, premise text (`idea`), genre, tone, target duration, and any existing entity counts.

---

## Step 3: Author the Complete Creative Package

Acting as the Film Director, Screenwriter, and Cinematographer, construct a JSON payload with the following components:

### 1. Project Metadata
Refine or preserve:
- `genre`: e.g. `"Adventure / Children's Animated"`, `"Cyberpunk Thriller"`
- `tone`: e.g. `"Warm, vibrant, cinematic 3D Pixar-style"`, `"Dark, neo-noir, atmospheric"`
- `target_duration`: e.g. `"1 minute"` (or `"30s"`, `"2m"`)

### 2. Story Beats (`beats`)
Decompose the premise into sequential dramatic beats:
- Typically **5–6 beats** for a 1-minute film.
- Each beat has `order_index`, `title`, and `description`.

### 3. Characters (`characters`)
Define every speaking or key character:
- `name`: Full character name.
- `role`: e.g. `"Protagonist / Lead"`, `"Supporting / Best Friend"`, `"Antagonist"`, `"Mentor"`.
- `age`: e.g. `"8 years old"`.
- `appearance`: Distinctive clothing, signature color, facial traits, hairstyle.
- `personality`: Behavioral cues, temperament.
- `consistency_prompt`: **Krea 2 optimized image prompt** (Character turnaround reference sheet with multiple angles: front full body, side profile, three-quarter, and close-up portrait on a clean seamless neutral studio backdrop, soft diffuse lighting, natural descriptive language without tag soup).

### 4. Locations (`locations`)
Define every environment featured in the story:
- `name`: Location name.
- `description`: Physical layout, time of day, atmosphere, textures.
- `consistency_prompt`: **Krea 2 optimized environment prompt** (Wide-angle establishing shot, clear readable spatial depth, atmospheric volumetric lighting, rich textures, no people, no text).

### 5. Items (`items`)
Define key narrative props:
- `name`, `description`.
- `consistency_prompt`: **Krea 2 optimized hero prop prompt** (Isolated studio product shot on a clean neutral grey backdrop, soft directional key lighting, tactile textures, no text).

### 6. Screenplay Scenes & Clips (`scenes`)
Break the story into scenes:
- `order_index`: 1-based index.
- `heading`: Standard slugline (`EXT. [LOCATION] - [TIME]` or `INT. [LOCATION] - [TIME]`).
- `location_name`: Exact name of one of the defined locations.
- `character_names`: List of character names present in the scene.
- `duration_sec`: Scene duration (e.g., 12 seconds for 2 clips of 6s).
- `action`: Present-tense cinematic prose describing the visual actions and events.
- `dialog`: Formatted screenplay dialog lines (`CHARACTER: Line...`).
- `clips`: Array of discrete shot units:
  - `order_index`: 1, 2, ...
  - `shot_size`: Cinematographic framing (`WideShot`, `MediumWideShot`, `MediumShot`, `MediumCloseUp`, `CloseUp`, `ExtremeCloseUp`).
  - `duration_sec`: 5–8 seconds per shot (typically 6s).
  - `dialog_lines_covered`: 1-based array of dialog line numbers spoken during this shot (e.g. `[1]`, `[2, 3]`).
  - `chain_from_prev`: Set to `true` for shot 2+ if it continues camera motion from the prior shot.
  - `description`: Detailed shot description (camera movement, character actions, blocking).
  - `prompt_draft`: **Official MiniMax H3 6-section optimized video prompt** (`subject_definitions:`, `summary:`, `retention_analysis:`, `detailed_description:`, `overall_soundscape:`, `non_diegetic_music:`).

For detailed prompting guidelines, see [references/screenplay_and_prompts.md](./references/screenplay_and_prompts.md).
For a sample payload schema, see [examples/sample_package.json](./examples/sample_package.json).

---

## Step 4: Ingest into Calliope

Write the authored package to a temporary file (e.g., `<appDataDir>/brain/<conversation-id>/scratch/staged_package.json`), then execute:

```bash
.agents/skills/calliope-director/scripts/director.py ingest <project_id> --file <path_to_package.json> [--overwrite]
```

Use `--overwrite` if the user wants to re-draft or replace an existing setup.

The script will:
- Insert all story beats, cast, locations, items, scenes, and clips in a single SQLite transaction.
- Link characters to scenes (`scene_characters`).
- Pre-populate `video_settings` with `(Input:prompt)` and `prompt_draft`.
- Update project status to `'in_progress'`.

---

## Step 5: Deliver Executive Summary

Present the results cleanly to the user:
1. **Film Overview**: Title, Genre, Tone, Target Runtime, and Cast list.
2. **Scenes & Coverage**: Scene breakdown with shot sizes and duration.
3. **Direct Stage Links**:
   - 📖 **Story Stage**: `http://127.0.0.1:5173/project/<id>?stage=story` (review beats and characters)
   - 🎨 **Assets Stage**: `http://127.0.0.1:5173/project/<id>?stage=assets` (ready to render character sheets & locations)
   - 🎬 **Script Stage**: `http://127.0.0.1:5173/project/<id>?stage=script` (inspect screenplay & coverage)
   - 🎥 **Video Stage**: `http://127.0.0.1:5173/project/<id>?stage=video` (all prompts staged, ready for ComfyUI generation)
