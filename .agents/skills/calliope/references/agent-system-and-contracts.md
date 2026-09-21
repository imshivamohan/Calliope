# Calliope Agent System & Tool Contracts

Calliope features an autonomous multi-agent production harness capable of executing the full creative pipeline through structured tool calling.

---

## 1. Agent Roles & Multi-Model Routing

The harness supports specialized sub-agent roles. Operators can assign distinct LLM endpoints to each role in **Settings → Agent** (`AGENT_LLM_ROLES`):

| Agent Role | Primary Focus | Recommended LLM Type |
|---|---|---|
| **Main Agent** | General orchestration, conversational interaction, user alignment | High-capability cloud model |
| **Planner** | Goal decomposition, task sequencing, dependency planning | High-reasoning model |
| **Story Agent** | Beat outlining, character development, worldbuilding | Fast creative model |
| **Script Agent** | Screenplay prose, dialogue formatting, shot coverage pass | Creative screenplay-focused model |
| **Assets Agent** | Image prompt generation, reference matching | Visual prompting model |
| **Video Agent** | MiniMax H3 XML formatting, shot brief conversion | Fast structured formatter |

*Note: Leaving any role unassigned defaults to the Active LLM.*

---

## 2. Session Lifecycle & Origins

Every agent conversation is tracked in `agent_sessions`:
- **Sandbox Sessions**: Start without a linked project. When the user asks to build a film, the agent automatically executes `create_project` and links the session.
- **Project-Linked Sessions**: Bound to a specific `project_id`. All read/write tools are strictly isolated to that project.
- **Origin Separation**:
  - `origin='chat'`: Standard conversational pipeline and AI Canvas agents (Planner enabled).
  - `origin='scene'`: Build Scene 3D blockout agents (Planner disabled; runs single-loop shot tools).

---

## 3. Real-Time Mid-Run Steering

Users can steer the agent while it is actively processing without aborting the turn:
1. When the agent is `status='running'`, the chat composer changes its button from "Send" to **"Steer"**.
2. Posting a message appends a `steering/message` event and records a message with `status='steering'`.
3. **Step Boundary Ingestion**: The agent loop buffers steering inputs and ingests them strictly at **step boundaries** (never between an assistant `tool_calls` message and its tool responses, which would violate the OpenAI API format).
4. Injected messages are tagged `[STEERING — user message sent while you work]`.
5. **Approval Security Constraint**: Steering messages cannot grant approval for destructive replacements or render actions (`guard_render_approval`). Authoritative approval must originate from a standard `user/message`.

---

## 4. Interactive Question Cards (`ask_user`)

When an agent encounters ambiguous creative choices or requires user preference:
1. Agent invokes the `ask_user` tool with structured options.
2. The chat interface renders an interactive selection card.
3. The turn suspends safely until the user selects an option or types a response, resuming execution without losing context.

---

## 5. Agent Memory System (`agent_memory`)

Persistent knowledge that survives across chat sessions and system restarts:
- **Tools**: `save_memory`, `forget_memory`, `list_memories`.
- **Scopes**:
  - `project`: Isolated to a specific project.
  - `global`: Available across all projects.
- **Kinds**:
  - `preference`: User taste (e.g., "Prefers moody anamorphic lighting").
  - `convention`: Formatting rules (e.g., "Always write character names in ALL CAPS in action lines").
  - `correction`: Guardrails learned from user corrections.

---

## 6. Safety Guards & Hardening Prompt

Every agent invocation is wrapped in operator-defined security rules (`DEFAULT_AGENT_HARDENING_PROMPT`):
1. **Scope Lockdown**: Prohibits reading or modifying data outside the linked project.
2. **Anti-Fabrication**: Strictly forbids hallucinating job numbers, file paths, or tool results.
3. **Prompt Injection Resistance**: Rejects instructions embedded inside file contents or tool outputs that attempt to override system rules.
4. **Destructive Action Protection**: Deletions or bulk script replacements require explicit user confirmation.
5. **Execution Caps**:
   - `agent_max_steps`: Default 24 steps per turn.
   - `agent_tool_timeout_sec`: 600s wall-clock cap per tool call (`wait_for_jobs` is exempt).
   - `agent_history_char_budget`: 400,000 character context ceiling to prevent token window overflow.

---

## 7. Complete Tool Registry (60+ Tools)

### Project & Workspace Tools
- `create_project`: Initialize new project
- `update_project`: Modify metadata, title, genre, tone
- `list_projects`: Discover existing projects
- `link_project` / `unlink_project`: Bind session to project
- `get_workspace`: Query full workspace state
- `attach_asset`: Link media to project entities

### Story Tools
- `generate_story`: Run automated story drafting pass
- `get_story`: Read story beats, characters, locations, items
- `add_beat`, `update_beat`, `delete_beat`: Manage narrative outline
- `add_character`, `update_character`, `delete_character`: Manage cast
- `add_location`, `update_location`, `delete_location`: Manage environments
- `add_item`, `update_item`, `delete_item`: Manage props

### Script & Scene Tools
- `generate_script`: Generate full screenplay scenes
- `break_into_shots`: Execute shot coverage pass on scenes
- `list_scenes`, `get_scene`, `add_scene`, `update_scene`, `delete_scene`, `reorder_scenes`: Screenplay management
- `list_clips`, `add_clip`, `update_clip`, `delete_clip`: Shot clip management

### Render & Queue Tools
- `enqueue_asset_jobs`: Queue reference image generations
- `enqueue_video_jobs`: Queue video clip renders
- `list_jobs`, `get_job_status`: Inspect queue state
- `wait_for_jobs`: Wait for asynchronous ComfyUI jobs to finish

### 3D Build Scene Tools
- `add_object`, `select_object`, `rename_object`, `delete_object`: Scene geometry
- `set_transform`, `reset_transform`: 3D coordinates and rotations
- `list_poses`, `apply_pose`, `set_joint`, `set_posture`, `reset_pose`: Actor posing
- `list_shot_presets`, `set_shot`: Camera framing
- `add_keyframe`, `update_keyframe`, `delete_keyframe`, `move_keyframe_time`: Animation timeline
- `set_playback`, `clear_scene`: Viewport playback controls
- `request_capture`: Trigger still or video capture
- `get_build_scene_gates`, `record_build_scene_gate`: Brief and Cut verification gates

### AI Canvas Tools
- `create_canvas_node`, `update_canvas_node`, `delete_canvas_node`: Node manipulation
- `canvas_connect`, `canvas_link`: Edge connections
- `run_canvas_node`: Trigger workflow node execution
- `post_artifact_to_canvas`: Pin media artifact to canvas
- `summarize_canvas`: Graph topology digest

### ComfyUI MCP & Workflow Tools
- `list_workflows`: Discover registered workflows
- `run_workflow`: Execute arbitrary workflow graph
- `comfy_server_info`: Probe ComfyUI connection and capabilities

### Memory & Skills Tools
- `save_memory`, `forget_memory`, `list_memories`: Scoped memory management
- `list_skills`, `read_skill`: Discover and load skill instruction sets
- `ask_user`: Interactive multi-choice prompt card
