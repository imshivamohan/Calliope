# Calliope Build Scene & 3D Shot Composer

**Build Scene** (`/build-scene`) is a browser-based 3D shot composer for blocking out cinematic shots, staging actors, positioning cameras, and timing motion before generating AI images or video.

---

## 1. Architecture: The Single Composition Surface

Build Scene adheres to a strict single-surface principle:
- One composition document (`scene_json` in the `shot_composition` database table) drives both the preview canvas and final video export.
- The **Three.js viewport is the single surface**:
  1. It renders the interactive real-time 3D preview.
  2. It captures high-resolution still frames.
  3. It executes deterministic `MediaRecorder` video export passes along the timeline.
- Exports are recorded as client WebM video and normalized server-side to **H.264 MP4 via FFmpeg**, guaranteeing that downstream workflows (Playground, ComfyUI `LoadVideo`) receive compliant MP4 files.

---

## 2. Left Session Rail & Scene Isolation

- The left rail displays independent composition sessions (`Scene · 1`, `Scene · 2`, ...).
- Each entry is bound to an `agent_session` record with `origin='scene'`.
- **Blind Isolation**: Scene sessions are kept completely separate from conversational AI Canvas chats (`origin='chat'`). The Build Scene agent loop runs a specialized single-loop harness with shot builder tools enabled and planner disabled.

---

## 3. Staging: Mannequins, Props & Poses

Actors in the 3D scene are represented by posable mannequins (`mannequin-js` / Three.js).

### Tools & Capabilities
- **Object Manipulation**:
  - `add_object`: Add actors, cameras, or geometric props.
  - `set_transform` / `reset_transform`: Position (`x, y, z`), Rotation (`pitch, yaw, roll`), Scale.
  - `rename_object`, `delete_object`, `select_object`.
- **Anatomy & Posture Controls**:
  - `list_poses`: Discover built-in pose presets (e.g., standing, seated, running, crouching, aiming, pointing).
  - `apply_pose`: Apply standard pose preset to a mannequin.
  - `set_joint`: Fine-tune individual joint angles (head, torso, shoulder, elbow, wrist, hip, knee, ankle).
  - `set_posture` / `reset_pose`: Global posture adjustments.

---

## 4. Timeline & Camera Framing

- **Framing Contract**: Camera framing is fundamentally the user's creative responsibility. The agent animates objects and actors through `shot_*` tools, but does not dictate user camera beats.
- **Keyframe Tracks**:
  - `add_keyframe`: Record transform or joint state at timestamp $T$.
  - `update_keyframe` / `delete_keyframe`: Adjust interpolation or values.
  - `move_keyframe_time`: Shift keyframes along the playback timeline.
- **Camera Presets**: `list_shot_presets` and `set_shot` allow applying standard camera setups:
  - Wide Master, Two-Shot, Over-The-Shoulder (OTS), Medium Close-Up (MCU), Extreme Close-Up (ECU), Low-Angle Hero, High-Angle Bird's Eye, Dutch Angle.

---

## 5. Agent Gates: Brief & Cut

To ensure agent actions are intentional and verified, the agent loop enforces two gates:

```
[Agent Turn Start] 
        |
        v
[Gate 1: Brief Gate]  <-- Agent must call `record_build_scene_gate('brief')`
        |                 before mutating scene objects/transforms
        v
[Scene Mutations]     <-- `add_object`, `set_transform`, `apply_pose`, etc.
        |
        v
[Gate 2: Cut Gate]    <-- Agent must call `record_build_scene_gate('cut')`
        |                 before requesting still captures or video export
        v
[Capture / Export]    <-- `request_capture`
```

Attempting to mutate objects before clearing the **Brief Gate** or requesting captures before clearing the **Cut Gate** causes the harness policy to reject the action with `guard_destructive_replace` or `guard_render_approval`.

---

## 6. Captures & Playground Integration

- Still captures and exported video tracks are stored in `calliope-backend/data/assets/shots/` and indexed in `shot_capture`.
- Captured stills and videos can be directly pulled into the **Playground** or project **Assets** stage using the **"From Build Scene"** asset picker.
