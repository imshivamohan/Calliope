# Screenplay, Cinematography, and Prompt Engineering Guidelines for Calliope

This guide defines the production standards for Antigravity acting as Film Director, Screenwriter, and Cinematographer. It establishes optimization protocols for **Krea 2** image generation (assets) and **MiniMax H3** video diffusion generation (clips).

---

## 1. Narrative Architecture & Duration Math

Calliope films are rendered in short, cohesive clips (typically 5–8 seconds each).
When directing a film based on the user's premise, calculate the scene and shot structure from `target_duration`:

- **30 seconds film**: 3–4 scenes, 5–6 clips total (~5–6s per clip).
- **1 minute film (60s)**: 4–6 scenes, 10–12 clips total (~6s each).
- **2 minute film (120s)**: 6–8 scenes, 16–20 clips total.

Each scene represents a dramatic location or beat shift. Each clip is a discrete camera setup (shot).

---

## 2. Screenplay Standards

- **Scene Headings (Sluglines)**: Always use standard screenplay format:
  `EXT. [LOCATION] - [TIME OF DAY]` or `INT. [LOCATION] - [TIME OF DAY]`
  Examples:
  - `EXT. VILLAGE ROAD - MORNING`
  - `INT. CAR INTERIOR - DAY`
  - `EXT. VILLAGE POND - AFTERNOON`
- **Action Blocks**: Present-tense, visual, concise prose. Describe what the camera sees and character actions/gestures. Avoid unfilmable internal thoughts. Always include motion, lighting, and wardrobe anchors.
- **Dialog**: Tagged with character names in uppercase (`CHARACTER_NAME: dialog`). In Calliope's database, dialog lines are tracked by 1-based line numbers, mapped into clips via `dialog_lines_covered: [1, 2]`.

---

## 3. Cinematographic Shot Sizes & Directing Vocabulary

Every clip must have an intentional `shot_size`:

| Shot Size | Directorial Purpose | Camera Framing & Motion |
| :--- | :--- | :--- |
| `WideShot` | Establishes environment, spatial orientation, scope. | Full body of characters, extensive background scenery. Smooth tracking or slow push-in. |
| `MediumWideShot` | Group interactions, movement through space. | Characters framed from knees up, balanced environment. |
| `MediumShot` | Conversation, emotional clarity, prop interactions. | Characters from waist up, legible gestures and expressions. Eye-level or slight Dutch angle. |
| `MediumCloseUp` | Rising emotional intensity, decisive dialogue lines. | Chest up framing, nuanced facial reactions. Subtle push-in. |
| `CloseUp` | Climax of emotion, significant prop reveals, intimacy. | Face fills frame, micro-expressions, key prop focus. Shallow depth of field. |
| `ExtremeCloseUp` | Heightened tension, critical tactile details. | Eyes, glistening tear, speedometer, key prop mechanism. Macro lens framing. |

---

## 4. Krea 2 Image Generation Prompt Optimization (Assets Stage)

Krea 2 is an advanced diffusion / flow-matching model that excels with **clean natural language descriptions** rather than legacy comma-separated tag soup.

### Core Krea 2 Principles:
1. **Natural Language Syntax**: Write descriptive, grammatical sentences. Avoid keyword spam (`"masterpiece, best quality, 8k, photorealistic, trending on artstation"` degrades Krea 2 quality).
2. **Explicit Visual Cues**: Explicitly describe subject wardrobe, materials, textures, facial features, and lighting angles.
3. **Internal Stylistic Consistency**: Keep prompts stylistically unified (e.g. consistently specify `"warm cinematic 3D animation style with clean silhouettes and soft volumetric lighting"` or `"35mm cinematic film still, anamorphic lens"`).
4. **Clean Studio Isolation for Reference Sheets**: For character turnaround sheets and props, specify a clean neutral studio backdrop so the ComfyUI background doesn't bleed into reference embeddings.

### Krea 2 Asset Templates:

#### Character Turnaround / Reference Sheet
```text
Character turnaround reference sheet of [Character Name], a [Age]-year-old [Heritage/Role] with [Hair Style/Color], [Facial Features], and [Expression]. Wearing [Specific Wardrobe & Colors, Fabric Textures]. Multiple views on a clean, seamless neutral grey studio backdrop: front full body, side profile, three-quarter view, and a close-up portrait. Neutral standing pose, soft diffuse studio lighting, clean silhouette, sharp details, [Aesthetic Style Anchor, e.g. warm cinematic 3D animation style].
```

#### Character Portrait
```text
Cinematic close-up portrait of [Character Name], [Brief Role/Age], featuring [Distinct Facial Features, Hair, Expression]. Wearing [Wardrobe Collar/Neckline Details]. Framed at eye-level, shallow depth of field with a softly blurred background, gentle warm key light highlighting facial contours, rich skin and fabric textures, [Aesthetic Style Anchor].
```

#### Location / Environment Reference
```text
Wide-angle establishing landscape of [Location Name], showing [Physical Layout, Key Landmarks, Foliage/Architecture]. [Atmosphere and Weather, e.g. gentle morning breeze, golden hour sunlight breaking through trees]. Clear, readable spatial depth for characters to stand in, rich natural materials, harmonious color palette, no people, no text, [Aesthetic Style Anchor].
```

#### Item / Hero Prop Reference
```text
Hero prop reference of [Item Name], [Detailed Physical Description, Materials, Colors, Wear/Patina]. Centered studio product shot on a clean neutral matte background, soft directional studio lighting, tactile material textures, high-definition concept render, no characters, no text.
```

---

## 5. MiniMax H3 Video Prompt Optimization (Clips & Video Stage)

MiniMax H3 (Hailuo 02 / Ref2Video) is a cinematic video diffusion model that achieves character, environment, and camera consistency using an **official 6-section structured format**.

When generating clips in Calliope, every clip's prompt draft should be formatted using the 6 sections:

```text
subject_definitions:
<Subject 1> is the [character/environment/item] "[Name]" in <Picture 1>, with [visual attributes to retain].
<Subject 2> is the [character/environment/item] "[Name]" in <Picture 2>, with [visual attributes to retain].

summary:
[reference generation] [1-2 sentences summarizing the shot's dramatic action using the <Subject N> labels].

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - [specific visual traits, clothing, hair, and facial proportions].
<Subject 2> (appears in [Shot 1]): fully_preserved - [specific visual traits, materials, and colors].

detailed_description:
[1-2 sentences establishing cinematic style, camera rig, lighting, palette, and atmosphere].
[Shot 1] [Cinematography, framing, and camera movement, e.g. "Slow cinematic push-in at eye level"]. <Subject 1> [exact physical movement, gesture, blocking, and expression]. <Subject 2> [reaction, motion, or interaction]. [Environmental dynamics, e.g. dust motes drifting, wind rustling leaves].
<Subject 1> (S1) says, <d>[Language] [Spoken dialogue]</d>

overall_soundscape:
[Atmospheric environment sound, diegetic foley: footsteps, engine rumble, rustling leaves, water ripples, or "N/A"].

non_diegetic_music:
[Musical score description: instrumentation, tempo, emotional tone, e.g. "Warm acoustic guitar and light marimba, cheerful tempo", or "N/A"].
```

### MiniMax H3 Rules:
1. **Reference Numbering**: `<Subject 1>` corresponds to the image wired into ComfyUI's first reference slot (`<Picture 1>`). Scene characters come first, followed by location backdrop.
2. **Mandatory Summary Tag**: The `summary:` section **must** begin with `[reference generation]` (or `[reference generation + video continuation]` if chaining).
3. **Retention Analysis**: Explicitly state `fully_preserved - ...` for each subject appearing in `[Shot 1]`.
4. **Dialogue Tagging**: Use `<d>[Language] ...</d>` tags for dialogue (e.g. `<Subject 1> (S1) says, <d>[English] We're on our way!</d>`).
5. **No Negative Leaks**: Keep the prompt descriptive, focused on positive visual actions, camera kinematics, and physical lighting.

---

## 6. End-to-End Workflow: Krea 2 to MiniMax H3 Pipeline

```
[Antigravity Director]
       │
       ├─► 1. Krea 2 Optimized Prompts ──► Render Character Sheets & Locations in ComfyUI
       │                                         │
       │                                         ▼ (Produces reference images)
       │
       └─► 2. MiniMax H3 6-Section Prompts ──► Reference Images wired as <Picture 1>, <Picture 2>
                                                 │
                                                 ▼ (Produces temporally stable cinematic video clips)
```

By pairing **Krea 2** for ultra-clean, high-fidelity reference asset generation with **MiniMax H3** for 6-section reference video diffusion, Calliope achieves production-grade character and environment consistency across all shots.
