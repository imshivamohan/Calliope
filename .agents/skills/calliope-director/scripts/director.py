#!/usr/bin/env python3
"""Calliope Director CLI.

Allows Antigravity (AGY) to act as autonomous Film Director, Showrunner, Screenwriter,
and Cinematographer for Calliope projects:
- Read project premise and metadata directly from SQLite
- Generate and ingest dramatic story beats, cast, environments, items, screenplay, shot coverage
- Enforces Krea 2 optimization for all image generation (characters, environments, props)
- Enforces official 6-section MiniMax H3 optimization for all video diffusion prompts
- Inspect and summarize staged projects with direct browser stage URLs
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


def find_repo_root() -> Path:
    """Find Calliope repository root robustly."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "calliope-backend" / "data").is_dir() or (parent / "calliope-backend").is_dir():
            return parent
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "calliope-backend").is_dir():
            return parent
    return Path("/Users/ooha/Calliope")


def get_db(repo_root: Path) -> sqlite3.Connection:
    db_path = repo_root / "calliope-backend" / "data" / "calliope.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Krea 2 Prompt Optimization Helpers
# ---------------------------------------------------------------------------

def format_krea2_character_prompt(character: dict[str, Any], style_anchor: str = "warm cinematic 3D animation style") -> str:
    """Optimize character turnaround prompt for Krea 2 natural language understanding."""
    if character.get("consistency_prompt") and len(character["consistency_prompt"].strip()) > 30:
        return character["consistency_prompt"].strip()

    name = character.get("name", "Character")
    role = character.get("role", "")
    age = character.get("age", "")
    app = character.get("appearance", "")
    pers = character.get("personality", "")

    desc_bits = []
    if age:
        desc_bits.append(f"{age}-old")
    if role:
        desc_bits.append(role)
    role_desc = " ".join(desc_bits) or "character"

    lines = [f"Character turnaround reference sheet of {name}, a {role_desc}"]
    if app:
        lines.append(f"with {app}")
    if pers:
        lines.append(f", showing a {pers} disposition")

    lines.append(
        f". Multiple angles on a seamless neutral light-grey studio backdrop: full-body front view, side profile, "
        f"three-quarter view, and a close-up portrait with clear facial features. Neutral standing pose, soft diffuse "
        f"studio lighting, crisp silhouettes, clean fabric folds, {style_anchor}, no text."
    )
    return "".join(lines)


def format_krea2_location_prompt(location: dict[str, Any], style_anchor: str = "cinematic 3D animation aesthetic") -> str:
    """Optimize environment establishing prompt for Krea 2."""
    if location.get("consistency_prompt") and len(location["consistency_prompt"].strip()) > 30:
        return location["consistency_prompt"].strip()

    name = location.get("name", "Environment")
    desc = location.get("description", "")
    return (
        f"Wide-angle establishing landscape of {name}. {desc}. "
        f"Clear readable spatial depth for characters, atmospheric volumetric lighting, rich natural textures, "
        f"harmonious color grade, {style_anchor}, no people, no text."
    )


def format_krea2_item_prompt(item: dict[str, Any], style_anchor: str = "3D animated film asset") -> str:
    """Optimize item/hero prop prompt for Krea 2."""
    if item.get("consistency_prompt") and len(item["consistency_prompt"].strip()) > 20:
        return item["consistency_prompt"].strip()

    name = item.get("name", "Prop")
    desc = item.get("description", "")
    return (
        f"Hero prop reference of {name}. {desc}. "
        f"Centered studio product shot on a clean neutral grey backdrop, soft directional studio lighting, "
        f"tactile material textures, crisp details, {style_anchor}, no characters, no text."
    )


# ---------------------------------------------------------------------------
# MiniMax H3 (6-Section) Video Prompt Optimization Helpers
# ---------------------------------------------------------------------------

def format_minimax_h3_clip_prompt(
    clip: dict[str, Any],
    scene: dict[str, Any],
    scene_characters: list[dict[str, Any]],
    location_name: str | None = None,
    style_anchor: str = "Warm cinematic 3D animation style with natural volumetric lighting and clean camera kinematics.",
) -> str:
    """Synthesizes or validates the official 6-section MiniMax H3 full-reference prompt."""
    existing = clip.get("h3_prompt") or clip.get("h3_xml") or clip.get("minimax_h3") or clip.get("prompt_draft", "")
    if "subject_definitions:" in existing and "retention_analysis:" in existing and "detailed_description:" in existing:
        return existing.strip()

    # 1. Subject Definitions
    defs = []
    retentions = []
    for idx, c in enumerate(scene_characters, 1):
        cname = c.get("name", f"Character {idx}")
        capp = c.get("appearance") or c.get("consistency_prompt") or "distinct wardrobe and features"
        # Extract first sentence or 120 chars
        capp_brief = capp.split(".")[0].strip() if "." in capp else capp[:120].strip()
        defs.append(f'<Subject {idx}> is the character "{cname}" in <Picture {idx}>, with {capp_brief}.')
        retentions.append(f'<Subject {idx}> (appears in [Shot 1]): fully_preserved - facial features, hair, and wardrobe.')

    if location_name:
        loc_idx = len(defs) + 1
        defs.append(f'<Subject {loc_idx}> is the environment "{location_name}" in <Picture {loc_idx}>.')
        retentions.append(f'<Subject {loc_idx}> (appears in [Shot 1]): fully_preserved - spatial layout, lighting, and environmental atmosphere.')

    subj_defs_str = "\n".join(defs) if defs else "N/A"
    retention_str = "\n".join(retentions) if retentions else "N/A"

    # 2. Summary
    chain = bool(clip.get("chain_from_prev"))
    task_prefix = "[reference generation + video continuation]" if chain else "[reference generation]"
    shot_desc = (clip.get("description") or scene.get("action") or "").strip()
    summary_str = f"{task_prefix} {shot_desc}"

    # 3. Detailed Description
    shot_size = clip.get("shot_size", "MediumShot")
    camera_action = f"[Shot 1] {shot_size}, {shot_desc}."

    dialog_lines = []
    covered = clip.get("dialog_lines_covered", [])
    raw_dialog = scene.get("dialog", "")
    if covered and raw_dialog:
        lines = [l.strip() for l in raw_dialog.splitlines() if l.strip()]
        for line_no in covered:
            if 1 <= line_no <= len(lines):
                dline = lines[line_no - 1]
                if ":" in dline:
                    spk, speech = dline.split(":", 1)
                    spk, speech = spk.strip(), speech.strip()
                    # Match speaker to subject index
                    s_idx = None
                    for idx, c in enumerate(scene_characters, 1):
                        if c.get("name", "").lower() == spk.lower():
                            s_idx = idx
                            break
                    who = f"<Subject {s_idx}> (S{s_idx})" if s_idx else f"{spk} (S1)"
                    dialog_lines.append(f"{who} says, <d>[English] {speech}</d>")
                else:
                    dialog_lines.append(f"Narrator says, <d>[English] {dline}</d>")

    dialog_block = ("\n" + "\n".join(dialog_lines)) if dialog_lines else ""
    detailed_str = f"{style_anchor}\n{camera_action}{dialog_block}"

    # 4. Soundscape & Music
    soundscape = clip.get("soundscape", "Ambient environment audio, subtle physical movement foley, gentle breeze.")
    music = clip.get("music", "Cheerful, lighthearted acoustic score with warm melodic tones.")

    return (
        f"subject_definitions:\n{subj_defs_str}\n\n"
        f"summary:\n{summary_str}\n\n"
        f"retention_analysis:\n{retention_str}\n\n"
        f"detailed_description:\n{detailed_str}\n\n"
        f"overall_soundscape:\n{soundscape}\n\n"
        f"non_diegetic_music:\n{music}"
    )


# ---------------------------------------------------------------------------
# Database Queries & Management
# ---------------------------------------------------------------------------

def read_project(repo_root: Path, project_id: int, as_json: bool = False) -> dict[str, Any] | None:
    conn = get_db(repo_root)
    try:
        p = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not p:
            if as_json:
                print(json.dumps({"error": f"Project #{project_id} not found"}))
            else:
                print(f"[!] Error: Project #{project_id} not found.")
            return None

        data = dict(p)
        beats = conn.execute("SELECT count(*) FROM story_beats WHERE project_id = ?", (project_id,)).fetchone()[0]
        chars = conn.execute("SELECT count(*) FROM characters WHERE project_id = ?", (project_id,)).fetchone()[0]
        locs = conn.execute("SELECT count(*) FROM locations WHERE project_id = ?", (project_id,)).fetchone()[0]
        items = conn.execute("SELECT count(*) FROM items WHERE project_id = ?", (project_id,)).fetchone()[0]
        scenes = conn.execute("SELECT count(*) FROM scenes WHERE project_id = ?", (project_id,)).fetchone()[0]
        clips = conn.execute("SELECT count(*) FROM clips WHERE project_id = ?", (project_id,)).fetchone()[0]

        counts = {
            "beats": beats,
            "characters": chars,
            "locations": locs,
            "items": items,
            "scenes": scenes,
            "clips": clips,
        }
        data["counts"] = counts

        if as_json:
            print(json.dumps(data, indent=2))
        else:
            print("=" * 75)
            print(f"🎬 Calliope Project #{project_id}: {data['title']}")
            print("=" * 75)
            print(f"Status:          {data['status']}")
            print(f"Genre:           {data['genre'] or 'Not specified'}")
            print(f"Tone:            {data['tone'] or 'Not specified'}")
            print(f"Target Duration: {data['target_duration'] or 'Not specified'}")
            print(f"Entities:        {beats} beats, {chars} characters, {locs} locations, {items} items")
            print(f"Screenplay:      {scenes} scenes, {clips} shot clips")
            print("-" * 75)
            print("Premise / Idea:")
            print(data.get("idea", "(No premise text provided)"))
            print("=" * 75)
        return data
    finally:
        conn.close()


def list_projects(repo_root: Path) -> None:
    conn = get_db(repo_root)
    try:
        rows = conn.execute(
            "SELECT id, title, genre, tone, target_duration, status, created_at FROM projects ORDER BY id DESC"
        ).fetchall()
        print(f"\nFound {len(rows)} Calliope Projects:")
        print("-" * 75)
        for r in rows:
            print(f"ID: {r['id']:<4} | Status: {r['status']:<11} | [{r['genre'] or 'No Genre'}] {r['title']} ({r['target_duration'] or '1m'})")
        print("-" * 75)
    finally:
        conn.close()


def ingest_package(
    repo_root: Path,
    package_path: Path,
    project_id: int | None = None,
    overwrite: bool = False,
) -> int:
    """Ingest a complete creative package into Calliope with Krea 2 & MiniMax H3 optimization."""
    with open(package_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = get_db(repo_root)
    try:
        with conn:
            proj_data = data.get("project", {})

            # 1. Project Resolution / Update
            if project_id is None:
                title = proj_data.get("title", "Untitled Film")
                idea = proj_data.get("idea", "")
                genre = proj_data.get("genre", "Adventure")
                tone = proj_data.get("tone", "Cinematic")
                target_duration = proj_data.get("target_duration", "1m")
                cur = conn.execute(
                    """
                    INSERT INTO projects (title, idea, genre, tone, target_duration, status)
                    VALUES (?, ?, ?, ?, ?, 'in_progress')
                    """,
                    (title, idea, genre, tone, target_duration),
                )
                project_id = cur.lastrowid
                print(f"[+] Created Project #{project_id}: '{title}'")
            else:
                updates = []
                params = []
                if "genre" in proj_data:
                    updates.append("genre = ?")
                    params.append(proj_data["genre"])
                if "tone" in proj_data:
                    updates.append("tone = ?")
                    params.append(proj_data["tone"])
                if "target_duration" in proj_data:
                    updates.append("target_duration = ?")
                    params.append(proj_data["target_duration"])

                updates.append("status = 'in_progress'")
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(project_id)

                sql = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)
                print(f"[*] Updating existing Project #{project_id}")

            # Overwrite cleanup if requested
            if overwrite:
                conn.execute("DELETE FROM story_beats WHERE project_id = ?", (project_id,))
                conn.execute("DELETE FROM items WHERE project_id = ?", (project_id,))
                scene_ids = [
                    r[0]
                    for r in conn.execute(
                        "SELECT id FROM scenes WHERE project_id = ?", (project_id,)
                    ).fetchall()
                ]
                for sid in scene_ids:
                    conn.execute("DELETE FROM scene_characters WHERE scene_id = ?", (sid,))
                conn.execute("DELETE FROM clips WHERE project_id = ?", (project_id,))
                conn.execute("DELETE FROM scenes WHERE project_id = ?", (project_id,))
                conn.execute("DELETE FROM characters WHERE project_id = ?", (project_id,))
                conn.execute("DELETE FROM locations WHERE project_id = ?", (project_id,))
                print(f"[*] Overwrite requested: cleared previous entities for Project #{project_id}")

            # 2. Story Beats
            beats = data.get("beats", [])
            for idx, beat in enumerate(beats, 1):
                conn.execute(
                    """
                    INSERT INTO story_beats (project_id, order_index, title, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (project_id, beat.get("order_index", idx), beat["title"], beat.get("description", "")),
                )
            if beats:
                print(f"[+] Ingested {len(beats)} story beats")

            # 3. Characters (Enforce Krea 2 optimization)
            characters = data.get("characters", [])
            char_map: dict[str, int] = {}
            char_records: dict[str, dict[str, Any]] = {}
            for c in characters:
                krea2_prompt = format_krea2_character_prompt(c)
                cur = conn.execute(
                    """
                    INSERT INTO characters (project_id, name, role, age, appearance, personality, consistency_prompt)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        c["name"],
                        c.get("role", "Lead"),
                        c.get("age", ""),
                        c.get("appearance", ""),
                        c.get("personality", ""),
                        krea2_prompt,
                    ),
                )
                char_map[c["name"]] = cur.lastrowid
                char_records[c["name"]] = {**c, "consistency_prompt": krea2_prompt}
            if characters:
                print(f"[+] Ingested {len(characters)} characters (Krea 2 optimized)")

            # 4. Locations (Enforce Krea 2 optimization)
            locations = data.get("locations", [])
            loc_map: dict[str, int] = {}
            for loc in locations:
                krea2_loc_prompt = format_krea2_location_prompt(loc)
                cur = conn.execute(
                    """
                    INSERT INTO locations (project_id, name, description, consistency_prompt)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        loc["name"],
                        loc.get("description", ""),
                        krea2_loc_prompt,
                    ),
                )
                loc_map[loc["name"]] = cur.lastrowid
            if locations:
                print(f"[+] Ingested {len(locations)} locations (Krea 2 optimized)")

            # 5. Items (Enforce Krea 2 optimization)
            items = data.get("items", [])
            for item in items:
                krea2_item_prompt = format_krea2_item_prompt(item)
                conn.execute(
                    """
                    INSERT INTO items (project_id, name, description, consistency_prompt)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        item["name"],
                        item.get("description", ""),
                        krea2_item_prompt,
                    ),
                )
            if items:
                print(f"[+] Ingested {len(items)} items (Krea 2 optimized)")

            # 6. Scenes & Clips (Enforce MiniMax H3 6-section optimization)
            scenes = data.get("scenes", [])
            total_clips = 0
            for s_idx, scene in enumerate(scenes, 1):
                loc_name = scene.get("location_name")
                loc_id = loc_map.get(loc_name) if loc_name else scene.get("location_id")

                cur = conn.execute(
                    """
                    INSERT INTO scenes (project_id, order_index, heading, action, dialog, duration_sec, location_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        scene.get("order_index", s_idx),
                        scene.get("heading", f"SCENE {s_idx}"),
                        scene.get("action", ""),
                        scene.get("dialog", ""),
                        scene.get("duration_sec", 10),
                        loc_id,
                    ),
                )
                scene_id = cur.lastrowid

                # Link Characters to scene
                active_scene_chars = []
                for char_name in scene.get("character_names", []):
                    cid = char_map.get(char_name)
                    if cid:
                        conn.execute(
                            "INSERT OR IGNORE INTO scene_characters (scene_id, character_id) VALUES (?, ?)",
                            (scene_id, cid),
                        )
                        if char_name in char_records:
                            active_scene_chars.append(char_records[char_name])

                # Clips
                scene_clips = scene.get("clips", [])
                for c_idx, clip in enumerate(scene_clips, 1):
                    # Format MiniMax H3 6-section prompt
                    h3_prompt = format_minimax_h3_clip_prompt(
                        clip, scene, active_scene_chars, location_name=loc_name
                    )

                    video_settings = {
                        "prompt_draft": h3_prompt,
                        "h3_prompt": h3_prompt,
                        "prompt_draft_meta": {
                            "based_on": clip.get("description", scene.get("action", "")),
                            "profile": "minimax_h3_ref",
                        },
                        "input_values": {
                            "(Input:prompt)": h3_prompt,
                        },
                    }

                    cov = clip.get("dialog_lines_covered", [])
                    cov_json = json.dumps(cov) if cov else None

                    conn.execute(
                        """
                        INSERT INTO clips (
                            scene_id, project_id, order_index, description, shot_size,
                            dialog_lines_covered, duration_sec, video_settings_json, chain_from_prev
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            scene_id,
                            project_id,
                            clip.get("order_index", c_idx),
                            clip.get("description", ""),
                            clip.get("shot_size", "MediumShot"),
                            cov_json,
                            clip.get("duration_sec", 6),
                            json.dumps(video_settings),
                            1 if clip.get("chain_from_prev") else 0,
                        ),
                    )
                    total_clips += 1

            print(f"[+] Ingested {len(scenes)} scenes and {total_clips} clips (MiniMax H3 optimized)")

        print(f"\n[SUCCESS] Project #{project_id} fully staged in Calliope!")
        print_stage_links(project_id)
        return project_id
    finally:
        conn.close()


def print_stage_links(project_id: int) -> None:
    base = f"http://127.0.0.1:5173/project/{project_id}"
    print("-" * 75)
    print("🚀 Project Stage URLs:")
    print(f"  • Overview: {base}")
    print(f"  • Story:    {base}?stage=story")
    print(f"  • Assets:   {base}?stage=assets (Krea 2 prompts staged)")
    print(f"  • Script:   {base}?stage=script")
    print(f"  • Video:    {base}?stage=video (MiniMax H3 6-section prompts staged)")
    print("-" * 75)


def export_project(repo_root: Path, project_id: int) -> dict[str, Any]:
    conn = get_db(repo_root)
    try:
        p = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not p:
            print(f"Error: Project #{project_id} not found")
            return {}
        result = {"project": dict(p)}
        result["beats"] = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM story_beats WHERE project_id = ? ORDER BY order_index",
                (project_id,),
            ).fetchall()
        ]
        result["characters"] = [
            dict(r) for r in conn.execute("SELECT * FROM characters WHERE project_id = ?", (project_id,)).fetchall()
        ]
        result["locations"] = [
            dict(r) for r in conn.execute("SELECT * FROM locations WHERE project_id = ?", (project_id,)).fetchall()
        ]
        result["items"] = [
            dict(r) for r in conn.execute("SELECT * FROM items WHERE project_id = ?", (project_id,)).fetchall()
        ]
        scenes = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM scenes WHERE project_id = ? ORDER BY order_index", (project_id,)
            ).fetchall()
        ]
        for s in scenes:
            s["clips"] = [
                dict(c)
                for c in conn.execute(
                    "SELECT * FROM clips WHERE scene_id = ? ORDER BY order_index", (s["id"],)
                ).fetchall()
            ]
        result["scenes"] = scenes
        return result
    finally:
        conn.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    repo_root = find_repo_root()
    parser = argparse.ArgumentParser(description="Calliope Director CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List all Calliope projects")
    sub.add_parser("list-projects", help="Alias for list")

    rp = sub.add_parser("read", help="Read project premise and current status")
    rp.add_argument("project_id", type=int, help="Calliope Project ID")
    rp.add_argument("--json", action="store_true", help="Output raw JSON")

    rp_alias = sub.add_parser("read-project", help="Alias for read")
    rp_alias.add_argument("project_id", type=int, help="Calliope Project ID")
    rp_alias.add_argument("--json", action="store_true", help="Output raw JSON")

    ip = sub.add_parser("ingest", help="Ingest a creative JSON package into a project")
    ip.add_argument("project_id", type=int, help="Calliope Project ID")
    ip.add_argument("--file", required=True, type=Path, help="Path to package JSON file")
    ip.add_argument("--overwrite", action="store_true", help="Clear existing beats/scenes before staging")

    ip_alias = sub.add_parser("ingest-package", help="Alias for ingest")
    ip_alias.add_argument("--file", required=True, type=Path, help="Path to package JSON file")
    ip_alias.add_argument("--project-id", dest="project_id", type=int, default=None, help="Calliope Project ID")
    ip_alias.add_argument("--overwrite", action="store_true", help="Clear existing beats/scenes before staging")

    ep = sub.add_parser("export", help="Export project to JSON")
    ep.add_argument("project_id", type=int, help="Calliope Project ID")

    ep_alias = sub.add_parser("export-project", help="Alias for export")
    ep_alias.add_argument("--project-id", dest="project_id", required=True, type=int, help="Calliope Project ID")

    lp = sub.add_parser("links", help="Print browser stage links for a project")
    lp.add_argument("project_id", type=int, help="Calliope Project ID")

    args = parser.parse_args()

    if args.cmd in ("list", "list-projects"):
        list_projects(repo_root)
    elif args.cmd in ("read", "read-project"):
        read_project(repo_root, args.project_id, args.json)
    elif args.cmd in ("ingest", "ingest-package"):
        ingest_package(repo_root, args.file, args.project_id, args.overwrite)
    elif args.cmd in ("export", "export-project"):
        data = export_project(repo_root, args.project_id)
        print(json.dumps(data, indent=2))
    elif args.cmd == "links":
        print_stage_links(args.project_id)
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
