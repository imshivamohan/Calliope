# AGY Director: Antigravity-Driven Creative Studio Workflow

This operational guide details how **Antigravity (agy CLI / your AI assistant)** takes complete ownership of all narrative, screenplay, shot breakdown, and prompt engineering tasks, completely bypassing local LLMs while reserving 100% of your local GPU/VRAM for ComfyUI.

---

## 1. The Division of Labor

```
+-------------------------------------------------------------------------------+
|                       ANTIGRAVITY (AGY CLI / ASSISTANT)                       |
|  - Story Premise, Themes, Pacing, and Dramatic Beat Sheets                    |
|  - Character Profiles & Visual Consistency Prompts                            |
|  - Environment & Location Design                                              |
|  - Screenplay Formatting (Action Prose & Verbatim Dialogue)                   |
|  - Shot Coverage Pass (Breaking scenes into ~5-10s clips #N.M)                |
|  - Shot Sizing (CU, MCU, MS, WS, OTS) & 1-based Dialogue Line Allocation       |
|  - ComfyUI Prompt Engineering (Prose & MiniMax H3 6-Section XML)              |
|  - Direct SQLite Staging via `director.py`                                    |
+---------------------------------------+---------------------------------------+
                                        | Populates calliope.db
                                        v
+-------------------------------------------------------------------------------+
|                        CALLIOPE WEB UI (Local Browser)                        |
|  - Visual Inspection of Story, Characters, Script, and Filmstrips             |
|  - One-Click Render Triggering to Local ComfyUI                               |
|  - Interactive Film View with FFmpeg Stitched Master Export                   |
+---------------------------------------+---------------------------------------+
                                        | Submits Workflows
                                        v
+-------------------------------------------------------------------------------+
|                            COMFYUI (Local Machine)                            |
|  - Dedicated 100% GPU VRAM (No local LLM memory contention)                  |
|  - Text-to-Image Generation (Flux, SDXL, Character Sheets)                    |
|  - Video Generation & Extend (MiniMax H3, CogVideoX, Wan2.1, Hunyuan)         |
+-------------------------------------------------------------------------------+
```

---

## 2. Why This Workflow is Superior

1. **Zero VRAM Contention**: Local LLMs (Ollama, LM Studio) consume 6–16 GB of VRAM. Running ComfyUI alongside a local LLM leads to out-of-memory errors, system slowdowns, and model thrashing. Offloading LLM tasks to Antigravity leaves all your GPU resources available for video diffusion.
2. **Hollywood-Grade Screenplay Quality**: Cloud/CLI Antigravity models (Gemini 3.8 Flash High) have vastly superior narrative coherence, character voice, screenplay formatting, and prompt crafting compared to small 3B/8B local models.
3. **Automated End-to-End Staging**: Antigravity writes the complete production package directly into Calliope's database in seconds. When you open Calliope Web, your story, characters, scenes, and clips are fully ready for video generation.

---

## 3. How to Use the AGY Director Workflow

### Step 1: Tell Antigravity What Film to Make
You simply give Antigravity your idea or ask it to flesh out an existing project. For example:
> *"Antigravity, take Project #2 ('Aadya and the Whispering Forest') and draft the complete story beats, cast, locations, full screenplay, and break each scene into shot clips with pre-computed prompts."*

### Step 2: Antigravity Crafts the Production Package
Antigravity formulates a complete `package.json` covering:
- **Project Metadata**: Title, genre, tone, target duration.
- **Story Beats**: Sequential narrative steps.
- **Characters**: Names, roles, appearances, and visual consistency prompts for ComfyUI.
- **Locations**: Descriptions and environment consistency prompts.
- **Screenplay Scenes**: Headings (`INT./EXT.`), action prose, dialogue.
- **Shot Coverage Clips**:
  - `shot_size`: CU, MCU, MS, WS, OTS.
  - `duration_sec`: 4–8 seconds.
  - `dialog_lines_covered`: 1-based indices of dialogue lines performed in that clip.
  - `chain_from_prev`: Continuation toggle for video extend takes.
  - `prompt_draft`: Tailored video generation prompt.
  - `h3_xml`: Full 6-section MiniMax H3 reference prompt.

### Step 3: Antigravity Ingests Directly into Calliope
Antigravity executes:
```bash
.agents/skills/calliope/scripts/director.py ingest-package --file /path/to/package.json --project-id <id>
```

### Step 4: Open Calliope & Generate
Open your browser at `http://127.0.0.1:5173/project/<id>`:
1. **Stage 1 (Story)**: Review the beats, characters, and environments.
2. **Stage 2 (Assets)**: Click Generate on any character to render reference portraits in your local ComfyUI.
3. **Stage 3 (Script)**: Review the screenplay and see how scenes are already broken into shot clips.
4. **Stage 4 (Video)**: All prompt drafts are pre-loaded in the inspector! Click **Generate** or **Generate All** to run your ComfyUI video workflows.
5. **Film View**: Once rendered, click **Export Film** to create the final 1080p stitched movie.
