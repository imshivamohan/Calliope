# Calliope ComfyUI Workflows & Role Contracts

Calliope does not hardcode ComfyUI node IDs. It discovers editable workflow parameters dynamically by parsing **role tags** in the titles of nodes from an **API-Format** workflow JSON.

---

## 1. Pure HTTP Integration Principles

Calliope connects to ComfyUI strictly through its standard HTTP REST API (`http://127.0.0.1:8188` by default):

1. **Asset Upload**: Sends reference images and audio files via `POST /upload/image` (with multipart form data and `subfolder=""`).
2. **Execution Queuing**: Patches the workflow JSON with user/scene values and submits via `POST /prompt`.
3. **Status Polling**: Polls `GET /history/{prompt_id}` at `queue_poll_interval_sec` (default 2s) up to `queue_poll_timeout_sec` (default 1800s / 30m, `0` for indefinite).
4. **Media Retrieval**: Fetches completed image and video outputs via `GET /view?filename=...&subfolder=...&type=...`.

> [!IMPORTANT]
> Calliope **never reads or writes ComfyUI's local file system directories directly**. All folder paths stay configured on the ComfyUI host.

---

## 2. Node Title Role Tagging Contract

When authoring or modifying workflows in ComfyUI, rename the input and output nodes so their display titles include a role tag:

```text
Display Title (Input:<role>)
Display Title (Output:<role>)
```

The display title before the parentheses can be anything (in any language). The `:<role>` inside parentheses is the contract recognized by Calliope.

### Canonical Input Roles

| Role | Supported Aliases | Auto-Filled By | Description |
|---|---|---|---|
| `prompt` | `positive` | Entity prompt, shot brief, H3 rewrite | Main positive generation prompt |
| `negative` | `neg` | Global / project negative prompt | Negative steering prompt |
| `width` | `w` | Form setting (default: 1024 / 1280) | Image/video horizontal resolution |
| `height` | `h` | Form setting (default: 1024 / 720) | Image/video vertical resolution |
| `character`| `char`, `portrait`, `sheet`, `face`, `ref` | Character portrait / sheet path | Character reference image input |
| `location` | `loc`, `environment`, `env`, `background`, `scene` | Location reference image path | Environment reference image input |
| `image` | `img` | Ordered reference slots | Generic image input (see Ordered Slots below) |
| `video` | `vid` | Previous clip / uploaded video | Input video file for extension (`LoadVideo`) |
| `audio` | `sound`, `sfx` | Scene voiceover or SFX file | Audio input (`LoadAudio`, `VHS_LoadAudio`) |
| `seed` | — | Random or locked integer | Noise seed |
| `duration` | `dur`, `length`, `seconds` | Clip / Scene estimated duration | Video duration in seconds |

### Canonical Output Roles

| Role | Supported Aliases | Consumed By |
|---|---|---|
| `image` | `img` | Character portraits, location references, canvas cards |
| `video` | `vid` | Shot clips, timeline playback, film export |

*Note: Unrecognized roles still render in the dynamic inspector form as generic inputs; they simply do not receive automatic entity auto-fill.*

---

## 3. Ordered Reference Slots & `<Subject N>` Mapping

For multi-reference workflows that accept multiple characters and environment references through generic `(Input:image)` slots:
1. Calliope sorts all generic image inputs by **ComfyUI node ID** in ascending order.
2. It fills slots with the scene's characters in **scene character order**, followed by the scene's location reference.
3. This exact sequence dictates `<Subject 1>`, `<Subject 2>`, etc. numbering inside the generation prompt.

---

## 4. Prompt Profiles

Each workflow can be assigned a prompt profile in Settings:

### 1. `minimax_h3_ref` (MiniMax H3 6-Section Reference Format)
Automatically rewrites the clip brief into MiniMax H3's structured XML/section specification:
- `<subject_definitions>`: Explicit definitions linking `<Subject 1>`, `<Subject 2>` to physical descriptions.
- `<summary>`: One-sentence dramatic premise of the take.
- `<retention_analysis>`: Visual elements to maintain from prior frames or references.
- `<detailed_description>`: Granular visual action, camera movements (Pan, Tilt, Dolly, Zoom), and lighting.
- `<overall_soundscape>`: Diegetic ambient environmental audio.
- `<non_diegetic_music>`: Score style and mood.
- Dialogue is embedded verbatim with language tags: `<d>[English] "Stop right there."</d>`.

#### Thinking Model Optimization (`h3_rewrite_extra_body`)
On reasoning/thinking LLMs (e.g. DeepSeek-R1, Qwen 2.5/3 Thinking), formatting prompts can waste thousands of reasoning tokens. Configure `h3_rewrite_extra_body` in settings to suppress reasoning during rewrites:
```json
{
  "h3_rewrite_extra_body": {
    "chat_template_kwargs": { "enable_thinking": false }
  }
}
```

### 2. `prose` (Default Plain Prose Format)
Combines scene slugline, shot description, and assigned dialogue lines into standard descriptive cinematic prose.

---

## 5. Video Continuation (Extend) Pattern

To chain clips seamlessly into long takes:
1. Workflow must contain a node tagged `(Input:video)` (typically `LoadVideo`).
2. Downstream nodes feed into video extend nodes (e.g., `MiniMaxH3EncodeAVPatched` → `MiniMaxH3VideoExtendPatched`).
3. Set the clip toggle to **Continue from previous clip**.
4. Choose clip source mode:
   - **Auto**: Timeline predecessor is picked dynamically when the job starts.
   - **Upload file**: Stored video from Playground uploads.
   - **From timeline**: Explicit past clip selection.

---

## 6. Error Diagnostics & Validation

Calliope inspects ComfyUI API responses for detailed failure causes:
- When ComfyUI returns HTTP 400 (`prompt_outputs_failed_validation`), Calliope extracts the node ID and error detail (e.g., `ComfyUI rejected workflow (400): node 12: Invalid audio file: "voice.m4a"`).
- Unreachable ComfyUI servers fail immediately without faking placeholder media unless `dry_run` is explicitly enabled.
