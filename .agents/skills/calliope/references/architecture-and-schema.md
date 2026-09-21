# Calliope Architecture & Schema Reference

Calliope is a local-first story-to-video studio that orchestrates local and hosted LLMs, ComfyUI generative workflows, browser-based 3D scene composition, and FFmpeg media assembly.

---

## 1. System Topology

```
+--------------------------------------------------------------------------+
|                          Web Browser (Client)                            |
|  SvelteKit 2 + Svelte 5 (Runes) + TailwindCSS + Three.js + @xyflow/svelte|
|  Ports: 5173 (Dev server proxies /api -> 8247)                           |
+------------------------------------+-------------------------------------+
                                     | HTTP REST & SSE (/api/events)
                                     v
+--------------------------------------------------------------------------+
|                          Calliope Backend                                |
|  FastAPI + Uvicorn (Port 8247)                                            |
|  - REST Routers (projects, story, scenes, assets, workflows, jobs, etc.) |
|  - SSE Event Bus (Broadcasts agent tokens, job progress, UI sync)        |
|  - Multi-Agent Harness (Main, Planner, Story, Script, Assets, Video)     |
|  - 60+ Built-in Tool Registry (DB, Canvas, 3D Blockout, Workflows)       |
|  - Queue Worker (Single/multi concurrency, HTTP polling, auto-retry)     |
|  - Media Engine (FFmpeg film stitching, normalization, frame matching)   |
+-------------------+--------------------+-------------------+-------------+
                    |                    |                   |
                    v                    v                   v
            +---------------+   +----------------+   +---------------+
            |  SQLite 3 WAL |   | ComfyUI Server |   | LLM Endpoints |
            |  calliope.db  |   | (HTTP-Only)    |   | (OpenAI API)  |
            +---------------+   +----------------+   +---------------+
```

---

## 2. Storage & Directory Layout

Calliope strictly anchors its data directory inside the application root (never `%TEMP%` or ephemeral system folders):

- **Config File**: `calliope-backend/calliope_config.json` (or root `calliope_config.json`).
- **Database**: `calliope-backend/data/calliope.db`.
- **Media Assets**: `calliope-backend/data/assets/`
  - `characters/`, `locations/`, `items/`: Generated entity reference portraits and sheets.
  - `clips/`: Rendered video clips.
  - `export/`: Stitched films.
  - `shots/`: 3D Build Scene captures (stills and normalized MP4s).
  - `playground/`: Custom user uploads and ad-hoc generation outputs.
- **Built-in Skills**: `calliope-backend/skills_builtin/` (shipped with the backend for subagents).

### Path Portability & Path Rebasing
On startup (`calliope.main:lifespan`), Calliope executes `rebase_stale_asset_paths()`. If the repository or folder was moved or opened across drive mounts, any absolute paths recorded in `calliope.db` are automatically rewritten to point to the current data directory without breaking media links.

---

## 3. Database Schema (19 Tables)

Calliope initializes SQLite with Write-Ahead Logging (`PRAGMA journal_mode = WAL`), a 10-second busy timeout (`PRAGMA busy_timeout = 10000`), and foreign keys enforced (`PRAGMA foreign_keys = ON`).

### Table Breakdown

#### 1. `projects`
Core project metadata and lifecycle state:
- `id` (INTEGER PRIMARY KEY)
- `title` (TEXT NOT NULL)
- `idea` (TEXT)
- `genre` (TEXT) — e.g. Drama, Sci-Fi, Horror, Noir, Action, Fantasy, Comedy
- `tone` (TEXT) — e.g. Gritty, Whimsical, Cynical, Epic, Melancholic, Satirical
- `target_duration` (TEXT) — e.g. "30s", "1m", "2m", "5m"
- `cover_path` (TEXT)
- `status` (TEXT DEFAULT 'draft') — 'draft', 'in_progress', 'completed'
- `created_at`, `updated_at` (TIMESTAMP)

#### 2. `story_beats`
Ordered narrative outline:
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `order_index` (INTEGER NOT NULL)
- `title` (TEXT NOT NULL)
- `description` (TEXT)
- `created_at` (TIMESTAMP)

#### 3. `characters`
Character definitions and visual consistency assets:
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `name` (TEXT NOT NULL)
- `role` (TEXT) — Protagonist, Antagonist, Supporting, etc.
- `age`, `appearance`, `personality` (TEXT)
- `portrait_path` (TEXT) — Primary character headshot
- `sheet_path` (TEXT) — Turnaround / expression sheet
- `consistency_prompt` (TEXT) — Prompt fragment for visual locking
- `created_at` (TIMESTAMP)

#### 4. `locations`
Environment descriptions and reference images:
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `name` (TEXT NOT NULL)
- `description` (TEXT)
- `reference_image_path` (TEXT)
- `consistency_prompt` (TEXT)
- `created_at` (TIMESTAMP)

#### 5. `items`
Props and key visual elements:
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `name` (TEXT NOT NULL)
- `description` (TEXT)
- `reference_image_path` (TEXT)
- `consistency_prompt` (TEXT)
- `created_at` (TIMESTAMP)

#### 6. `scenes`
Screenplay scenes (the narrative and script unit):
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `beat_id` (INTEGER REFERENCES story_beats(id) ON DELETE SET NULL)
- `order_index` (INTEGER NOT NULL)
- `heading` (TEXT) — Standard slugline (e.g. `EXT. NEON ALLEYWAY - NIGHT`)
- `action` (TEXT) — Full action prose
- `dialog` (TEXT) — Screenplay-formatted verbatim dialogue lines
- `duration_sec` (INTEGER) — Estimated scene duration
- `workflow_id` (INTEGER) — Default workflow assigned to scene
- `env_image_path` (TEXT) — Scene environment backdrop
- `location_id` (INTEGER) — Bound location entity
- `video_path` (TEXT) — Legacy / stitched scene video
- `video_settings_json` (TEXT) — Default input overrides
- `created_at` (TIMESTAMP)

#### 7. `scene_characters`
Many-to-many relationship linking characters present in each scene:
- `scene_id` (INTEGER REFERENCES scenes(id) ON DELETE CASCADE)
- `character_id` (INTEGER REFERENCES characters(id) ON DELETE CASCADE)
- PRIMARY KEY (`scene_id`, `character_id`)

#### 8. `clips` (The Video Generation Unit)
One script scene expands into $N$ shot clips through the coverage pass:
- `id` (INTEGER PRIMARY KEY)
- `scene_id` (INTEGER REFERENCES scenes(id) ON DELETE CASCADE)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `order_index` (INTEGER NOT NULL) — Order within the scene
- `description` (TEXT) — Specific visual action for this camera take
- `shot_size` (TEXT) — CU (Close-Up), MCU (Medium Close-Up), MS (Medium Shot), WS (Wide Shot), OTS (Over-The-Shoulder), POV, Extreme Close-Up
- `dialog_lines_covered` (TEXT) — JSON array or comma list of 1-based dialog line indices performed during this clip
- `duration_sec` (INTEGER) — Length of this clip in seconds (~5–10s)
- `workflow_id` (INTEGER) — Assigned video workflow
- `clip_path` (TEXT) — File path to generated video clip
- `video_settings_json` (TEXT) — Saved input parameters, overrides, and prompt drafts
- `chain_from_prev` (INTEGER DEFAULT 0) — Boolean flag: 1 = extend from previous clip (video continuation) instead of cutting fresh
- `created_at` (TIMESTAMP)

#### 9. `workflows`
Registered ComfyUI API-format workflow graphs:
- `id` (INTEGER PRIMARY KEY)
- `name` (TEXT NOT NULL)
- `kind` (TEXT NOT NULL CHECK(kind IN ('image', 'video')))
- `workflow_json` (TEXT NOT NULL) — API Format export from ComfyUI
- `input_node_map` (TEXT) — JSON mapping detected input roles to node IDs
- `output_node_name` (TEXT) — Output node identifier
- `input_schema` (TEXT) — JSON schema of discovered inputs
- `output_schema` (TEXT) — Discovered output types
- `description` (TEXT)
- `prompt_profile` (TEXT NOT NULL DEFAULT 'prose') — 'prose' or 'minimax_h3_ref'
- `is_enabled` (INTEGER NOT NULL DEFAULT 1)
- `created_at` (TIMESTAMP)

#### 10. `jobs`
Queue render executions:
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `scene_id` (INTEGER REFERENCES scenes(id) ON DELETE SET NULL)
- `clip_id` (INTEGER REFERENCES clips(id) ON DELETE SET NULL)
- `kind` (TEXT NOT NULL) — 'image', 'video', 'export'
- `workflow_id` (INTEGER REFERENCES workflows(id) ON DELETE SET NULL)
- `status` (TEXT DEFAULT 'pending') — 'pending', 'running', 'completed', 'failed', 'cancelled'
- `payload_json` (TEXT) — Exact parameters submitted to ComfyUI
- `output_paths_json` (TEXT) — Array of produced asset paths
- `error` (TEXT) — Honest error string if failed
- `created_at`, `started_at`, `completed_at` (TIMESTAMP)
- `retry_count` (INTEGER DEFAULT 0)

#### 11. `agent_sessions`
Conversational chat sessions:
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE SET NULL)
- `title` (TEXT NOT NULL DEFAULT 'New chat')
- `status` (TEXT DEFAULT 'idle') — 'idle', 'running', 'error'
- `origin` (TEXT DEFAULT 'chat') — 'chat' (AI Canvas / Production Agents) or 'scene' (3D Build Scene)
- `created_at`, `updated_at` (TIMESTAMP)

#### 12. `agent_messages`
Chat timeline:
- `id` (INTEGER PRIMARY KEY)
- `session_id` (INTEGER REFERENCES agent_sessions(id) ON DELETE CASCADE)
- `role` (TEXT NOT NULL) — 'user', 'assistant', 'tool', 'system'
- `content` (TEXT NOT NULL DEFAULT '')
- `agent_name` (TEXT) — Main, Planner, Story, Script, Assets, Video
- `tool_name` (TEXT)
- `tool_args_json` (TEXT)
- `tool_result_json` (TEXT)
- `status` (TEXT) — 'steering', 'complete', etc.
- `created_at` (TIMESTAMP)

#### 13. `agent_events`
Sequential event replay log per session:
- `id` (INTEGER PRIMARY KEY)
- `session_id` (INTEGER REFERENCES agent_sessions(id) ON DELETE CASCADE)
- `seq` (INTEGER NOT NULL)
- `type` (TEXT NOT NULL) — e.g. `user/message`, `steering/message`, `tool/call`, `tool/result`, `step/start`, `step/end`, `plan/created`, `turn/end`
- `data_json` (TEXT NOT NULL)
- `created_at` (TIMESTAMP)
- UNIQUE(`session_id`, `seq`)

#### 14. `canvas`
AI Canvas graph document:
- `id` (INTEGER PRIMARY KEY)
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `agent_session_id` (INTEGER REFERENCES agent_sessions(id) ON DELETE CASCADE)
- `title` (TEXT NOT NULL DEFAULT 'Untitled Canvas')
- `thumbnail_path` (TEXT)
- `viewport_json` (TEXT) — `{x, y, zoom}` coordinates
- `created_at`, `updated_at` (TIMESTAMP)

#### 15. `canvas_node`
Nodes on the AI Canvas surface:
- `id` (INTEGER PRIMARY KEY)
- `canvas_id` (INTEGER REFERENCES canvas(id) ON DELETE CASCADE)
- `type` (TEXT CHECK(type IN ('entity','image','video','text','workflow')))
- `title` (TEXT)
- `x`, `y`, `width`, `height` (REAL)
- `workflow_id` (INTEGER NULL)
- `artifact_path` (TEXT NULL)
- `job_id` (INTEGER NULL)
- `status` (TEXT DEFAULT 'idle')
- `input_values_json` (TEXT NOT NULL DEFAULT '{}')
- `entity_type` (TEXT NULL) — 'character', 'location', 'item'
- `entity_id` (INTEGER NULL)
- `deleted` (INTEGER DEFAULT 0)
- `created_at`, `updated_at` (TIMESTAMP)

#### 16. `canvas_edge`
Connections between canvas nodes:
- `id` (INTEGER PRIMARY KEY)
- `canvas_id` (INTEGER REFERENCES canvas(id) ON DELETE CASCADE)
- `src_node_id` (INTEGER REFERENCES canvas_node(id) ON DELETE CASCADE)
- `dst_node_id` (INTEGER REFERENCES canvas_node(id) ON DELETE CASCADE)
- `kind` (TEXT CHECK(kind IN ('data','link')))
- `label` (TEXT)
- `dst_role` (TEXT) — Target workflow input role (e.g. 'character', 'location')
- `dst_comfy_node_id` (TEXT)
- `created_at` (TIMESTAMP)

#### 17. `agent_memory`
Cross-session persistent knowledge:
- `id` (INTEGER PRIMARY KEY)
- `scope` (TEXT CHECK(scope IN ('global','project')))
- `project_id` (INTEGER REFERENCES projects(id) ON DELETE CASCADE)
- `content` (TEXT NOT NULL)
- `kind` (TEXT DEFAULT 'preference' CHECK(kind IN ('preference','convention','correction')))
- `source` (TEXT DEFAULT 'agent' CHECK(source IN ('agent','user')))
- `use_count` (INTEGER DEFAULT 0)
- `last_used_at` (TIMESTAMP)
- `created_at` (TIMESTAMP)
- UNIQUE(`scope`, `project_id`, `content`)

#### 18. `shot_composition`
3D Build Scene compositions:
- `id` (INTEGER PRIMARY KEY)
- `agent_session_id` (INTEGER UNIQUE REFERENCES agent_sessions(id) ON DELETE SET NULL)
- `title` (TEXT NOT NULL DEFAULT 'Untitled composition')
- `scene_json` (TEXT NOT NULL DEFAULT '{}') — Three.js scene graph, objects, mannequins, keyframes, camera tracks
- `capture_request_json` (TEXT) — Trigger for client-side viewport render
- `created_at`, `updated_at` (TIMESTAMP)

#### 19. `shot_capture`
Visual captures exported from 3D Build Scene:
- `id` (INTEGER PRIMARY KEY)
- `composition_id` (INTEGER REFERENCES shot_composition(id) ON DELETE CASCADE)
- `kind` (TEXT DEFAULT 'image' CHECK(kind IN ('image','video')))
- `label` (TEXT)
- `file_path` (TEXT) — Path to still image or normalized H.264 MP4
- `meta_json` (TEXT) — Camera metadata, timestamp, resolution
- `created_at` (TIMESTAMP)

---

## 4. Configuration Schema (`calliope_config.json`)

All configuration is loaded via Pydantic `BaseSettings` (`calliope.config.Settings`), supporting environment overrides with prefix `CALLIOPE_`:

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | str | `"127.0.0.1"` | Bind host |
| `port` | int | `8247` | Backend HTTP port |
| `data_dir` | Path | `BACKEND_ROOT / "data"` | Data directory root |
| `assets_dir` | Path | `data_dir / "assets"` | Media assets directory |
| `db_name` | str | `"calliope.db"` | SQLite filename |
| `llm_base_url` | str | `"http://127.0.0.1:11434/v1"` | Active LLM endpoint |
| `llm_model` | str | `"llama3.2"` | Active LLM model identifier |
| `llm_api_key` | str \| None | `None` | Active LLM API key |
| `llm_profiles` | list[dict] | `[]` | Multi-profile list of saved OpenAI endpoints |
| `llm_active_id` | str \| None | `None` | UUID of active profile |
| `agent_llm_assignments` | dict | `{}` | Role-to-profile map (`main`, `planner`, `story`, `script`, `assets`, `video`) |
| `comfyui_base_url` | str | `"http://127.0.0.1:8188"` | ComfyUI HTTP root |
| `queue_concurrency` | int | `1` | Max concurrent rendering jobs |
| `queue_poll_interval_sec` | float | `2.0` | Polling interval for ComfyUI `/history` |
| `queue_poll_timeout_sec` | float | `1800.0` | Job poll timeout (30 min; `0` = indefinite) |
| `queue_max_retries` | int | `2` | Auto-retries before job failure |
| `agent_max_steps` | int | `24` | Step limit per agent execution turn |
| `agent_tool_timeout_sec` | float | `600.0` | Single tool execution cap (`0` = off) |
| `agent_history_char_budget`| int | `400000` | Context token cap safeguard (~100k tokens) |
| `agent_hardening_prompt` | str | Default prompt | Operator-level system prompt security rules |
| `h3_rewrite_extra_body` | dict | `{}` | Injected payload for H3 rewrites (e.g. disable thinking) |
| `dry_run` | bool | `False` | When True, generates placeholder dummy media |

---

## 5. Real-Time Server-Sent Events (SSE)

The `/api/events` endpoint streams events to synchronize UI components with backend activity:

- `agent.message`: New chat message appended.
- `agent.token`: Streaming LLM response chunk.
- `agent.thinking`: Streaming chain-of-thought token.
- `agent.plan`: Planner task list created or updated.
- `agent.task`: Individual planner step start/complete.
- `agent.tool`: Tool invocation started/finished.
- `agent.session.updated`: Session status or title changed.
- `job.created`: Job queued.
- `job.started`: Worker submitted job to ComfyUI.
- `job.progress`: ComfyUI node execution progress.
- `job.completed`: Output media downloaded and verified.
- `job.failed`: Honest error surfaced.
- `job.deleted`: Job cancelled or pruned.
- `asset.ready`: Entity portrait/sheet ready.
- `story.ready`: Story generation completed.
- `canvas.updated`: Graph modified.
- `shot.updated`: 3D scene updated.
- `shot.capture.saved`: Viewport capture written to disk.
