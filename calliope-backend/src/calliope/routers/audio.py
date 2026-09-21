"""Audio & Voice Generation API router.

Supports generating character voice dialogue using Higgs Audio v3 on the
dedicated ComfyUI Audio instance.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from calliope import config
from calliope.audio.higgs import enqueue_clip_dialog_job
from calliope.db import get_db, row_to_dict

router = APIRouter()
logger = logging.getLogger("calliope.routers.audio")


class ClipVoiceRequest(BaseModel):
    text: str | None = None
    character_id: int | None = None
    engine: str = "higgs"  # "higgs" (4B Foundation) or "fish" (Fish Audio S2 Pro)
    voice_option: str = "reference"  # "reference", "male", "female"
    enhanced: bool = True


class ProjectDialogueRequest(BaseModel):
    engine: str = "higgs"
    voice_option: str = "reference"
    enhanced: bool = True


class CharacterVoiceSampleRequest(BaseModel):
    voice_sample_path: str


@router.post("/projects/{project_id}/clips/{clip_id}/generate-voice")
async def generate_clip_voice(
    project_id: int, clip_id: int, payload: ClipVoiceRequest | None = None
) -> dict[str, Any]:
    """Queue voice dialogue generation for a single clip."""
    text = payload.text if payload else None
    char_id = payload.character_id if payload else None
    engine = payload.engine if payload else "higgs"
    voice_opt = payload.voice_option if payload else "reference"
    enhanced = payload.enhanced if payload and payload.enhanced is not None else True

    job = enqueue_clip_dialog_job(
        project_id=project_id,
        clip_id=clip_id,
        text=text,
        character_id=char_id,
        engine=engine,
        voice_option=voice_opt,
        enhanced=enhanced,
    )
    if not job:
        raise HTTPException(
            status_code=400,
            detail="Could not generate voice for clip (no dialog text found or clip missing)",
        )
    return {"status": "queued", "job": job}


@router.post("/projects/{project_id}/generate-dialogue")
async def generate_project_dialogue(
    project_id: int, payload: ProjectDialogueRequest | None = None
) -> dict[str, Any]:
    """Queue voice dialogue generation for all clips in the project that cover dialogue."""
    engine = payload.engine if payload else "higgs"
    conn = get_db(config.settings.db_path)
    try:
        clips = conn.execute(
            """
            SELECT c.id, c.dialog_lines_covered, s.dialog
            FROM clips c JOIN scenes s ON s.id = c.scene_id
            WHERE c.project_id = ?
            ORDER BY s.order_index, c.order_index, c.id
            """,
            (project_id,),
        ).fetchall()
        queued_jobs = []
        for c in clips:
            raw = c["dialog_lines_covered"]
            has_covered = raw and raw not in ("[]", '""', "null")
            has_scene_dialog = bool(c["dialog"] and c["dialog"].strip())
            if not has_covered and not has_scene_dialog:
                continue
            voice_opt = payload.voice_option if payload else "reference"
            enhanced = payload.enhanced if payload and payload.enhanced is not None else True
            job = enqueue_clip_dialog_job(
                project_id=project_id,
                clip_id=c["id"],
                engine=engine,
                voice_option=voice_opt,
                enhanced=enhanced,
            )
            if job:
                queued_jobs.append(job)
        return {
            "status": "queued",
            "total_queued": len(queued_jobs),
            "jobs": queued_jobs,
        }
    finally:
        conn.close()


@router.post("/characters/{character_id}/voice-sample")
async def set_character_voice_sample(
    character_id: int, payload: CharacterVoiceSampleRequest
) -> dict[str, Any]:
    """Set the reference voice audio sample for a character."""
    conn = get_db(config.settings.db_path)
    try:
        row = conn.execute(
            "SELECT id FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Character not found")

        conn.execute(
            "UPDATE characters SET voice_sample_path = ? WHERE id = ?",
            (payload.voice_sample_path, character_id),
        )
        conn.commit()
        return {"status": "ok", "character_id": character_id, "voice_sample_path": payload.voice_sample_path}
    finally:
        conn.close()
