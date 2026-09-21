# Calliope AI Canvas, Playground & Asset Library

Beyond the linear 4-stage project pipeline, Calliope provides non-linear visual surfaces: the **AI Canvas**, the **Playground**, and the centralized **Asset Library**.

---

## 1. AI Canvas (`/canvas` & `/canvas/[id]`)

The AI Canvas is an infinite node-graph workspace powered by `@xyflow/svelte`, merging conversational agent workflows with spatial composition.

### Node Types

| Node Type | Database `type` | Description |
|---|---|---|
| **Entity Node** | `entity` | Visual representation of a Project Character, Location, or Item |
| **Image Node** | `image` | Rendered or uploaded still image artifact with preview thumbnail |
| **Video Node** | `video` | Video clip artifact with inline HTML5 video playback |
| **Text Node** | `text` | Screenplay notes, beats, ideas, or raw generation prompts |
| **Workflow Node** | `workflow` | Executable ComfyUI workflow block with dynamic parameter form |

### Connections (Edges)
- **Data Edges** (`kind='data'`): Pass data from output nodes into workflow input roles. For example, connecting an `entity` or `image` node into an input slot with `dst_role='character'` or `dst_role='location'`.
- **Link Edges** (`kind='link'`): Associative connections representing narrative or conceptual links.

### Direct Execution & Artifact Deduplication
- Clicking **Run** on a Workflow Node executes the workflow directly through the backend queue.
- **Deduplication Guard**: SQLite enforces a unique constraint on `(canvas_id, job_id)` for media nodes. This prevents twin cards when the agent's `post_artifact_to_canvas` tool call and the frontend auto-materializer race on job completion.

### Canvas Organization & Management
- **Auto-Tidy**: `POST /api/canvas/{id}/tidy` runs automated topological spacing to cleanly align nodes and remove wire clutter.
- **Honest Deletion**: `delete_canvas_node` removes the node and all attached edges from the SQLite database.

---

## 2. Playground (`/playground`)

The Playground is an ad-hoc sandbox for testing prompts, experimenting with new ComfyUI workflows, and processing media without project boundaries.

### Core Capabilities
- **Universal Workflow Execution**: Select any registered ComfyUI workflow, adjust inputs via dynamic forms, and trigger generations.
- **Direct File Uploads**: Upload arbitrary image, video, and audio files (`POST /api/playground/uploads`) for use as reference material or init video.
- **Attach to Project**:
  - Any successful generation in Playground can be linked to an existing project in one click (`POST /api/playground/attach`).
  - Destination targets: Character portrait, Character turnaround sheet, Location backdrop, Item reference, or Scene clip video.

---

## 3. Asset Library (`/library`)

The Asset Library is a unified media manager cataloging every asset generated or uploaded across all projects and sessions.

### Features
- **Categorized Filtering**: Filter assets by Project, Characters, Locations, Items, Playground Uploads, or 3D Build Scene Captures.
- **Lazy Loading & Virtualization**: Optimized grid handles hundreds of media files smoothly.
- **Inspection & Cleanup**: View high-resolution media previews, inspect metadata, download files, or delete unused assets.
- **Steering Library**: Store steering prompts and reference style images to maintain visual continuity across multiple projects.
