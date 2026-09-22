"""Tests for Higgs Audio v3 voice generation, audio routing, and dual-endpoint ComfyUI support."""
from __future__ import annotations

import json
import pytest

from calliope.audio.higgs import build_higgs_v3_prompt, enqueue_clip_dialog_job
from calliope.config import settings
from calliope.db import get_db


def test_build_higgs_v3_prompt_base():
    prompt = build_higgs_v3_prompt("Hello world from Calliope.")
    assert "1" in prompt
    assert prompt["1"]["class_type"] == "HiggsV3LoadModel"
    assert prompt["1"]["inputs"]["model"] == "higgs-audio-v3-tts-4b"
    assert "44" in prompt
    assert prompt["44"]["inputs"]["text"] == "Hello world from Calliope."
    assert "35" in prompt
    assert prompt["35"]["class_type"] == "HiggsV3Generate"
    assert "9" in prompt
    assert prompt["9"]["class_type"] == "SaveAudioMP3"


def test_build_higgs_v3_prompt_voice_clone(tmp_path):
    ref_audio = tmp_path / "voice_sample.mp3"
    ref_audio.write_bytes(b"mock audio bytes")

    prompt = build_higgs_v3_prompt("Cloned voice line.", reference_audio_path=str(ref_audio))
    assert "8" in prompt
    assert prompt["8"]["class_type"] == "LoadAudio"
    assert "5" in prompt
    assert prompt["5"]["class_type"] == "HiggsV3WhisperTranscribe"
    assert "35" in prompt
    assert prompt["35"]["class_type"] == "HiggsV3VoiceClone"
    assert "9" in prompt
    assert prompt["9"]["class_type"] == "SaveAudioMP3"


def test_build_fish_s2_prompt_voice_clone(tmp_path):
    from calliope.audio.higgs import build_fish_s2_prompt, build_voice_clone_prompt

    ref_audio = tmp_path / "sample.mp3"
    ref_audio.write_bytes(b"sample bytes")

    # Direct Fish Audio prompt
    prompt = build_fish_s2_prompt("[excited] Look at that!", reference_audio_path=str(ref_audio))
    assert "8" in prompt
    assert prompt["8"]["class_type"] == "LoadAudio"
    assert "12" in prompt
    assert prompt["12"]["class_type"] == "FishS2VoiceCloneTTS"
    assert prompt["12"]["inputs"]["model_path"] == "s2-pro-fp8"
    assert prompt["12"]["inputs"]["text"] == "[excited] Look at that!"
    assert "9" in prompt

    # Unified dispatcher
    dispatched_fish = build_voice_clone_prompt("Test line", reference_audio_path=str(ref_audio), engine="fish")
    assert dispatched_fish["12"]["class_type"] == "FishS2VoiceCloneTTS"

    dispatched_higgs = build_voice_clone_prompt("Test line", reference_audio_path=str(ref_audio), engine="higgs")
    assert dispatched_higgs["35"]["class_type"] == "HiggsV3VoiceClone"


def test_enqueue_clip_dialog_job(client):
    r = client.post("/api/projects", json={"title": "Audio Project"})
    pid = r.json()["id"]

    scene_r = client.post(
        f"/api/projects/{pid}/scenes",
        json={"order_index": 1, "heading": "INT. LAB - DAY", "dialog": "DOCTOR\nIt is alive!"},
    )
    scene = scene_r.json()
    clip_id = scene["clips"][0]["id"]

    job = enqueue_clip_dialog_job(pid, clip_id, text="It is alive!")
    assert job is not None
    assert job["kind"] == "voice"
    assert job["project_id"] == pid

    payload = json.loads(job["payload_json"])
    assert payload["audio_endpoint"] is True
    assert payload["dialog_text"] == "It is alive!"


def test_audio_router_endpoints(client):
    r = client.post("/api/projects", json={"title": "Audio Router Project"})
    pid = r.json()["id"]

    # 1. Create character and set voice sample
    char_r = client.post(f"/api/projects/{pid}/characters", json={"name": "Alice"})
    cid = char_r.json()["id"]

    vs_r = client.post(
        f"/api/characters/{cid}/voice-sample",
        json={"voice_sample_path": "/path/to/alice_sample.mp3"},
    )
    assert vs_r.status_code == 200
    assert vs_r.json()["voice_sample_path"] == "/path/to/alice_sample.mp3"

    # 2. Create scene and generate clip voice
    scene_r = client.post(
        f"/api/projects/{pid}/scenes",
        json={"order_index": 1, "heading": "INT. ROOM", "dialog": "ALICE\nGood morning."},
    )
    clip_id = scene_r.json()["clips"][0]["id"]

    v_r = client.post(
        f"/api/projects/{pid}/clips/{clip_id}/generate-voice",
        json={"text": "Good morning.", "character_id": cid},
    )
    assert v_r.status_code == 200
    assert v_r.json()["status"] == "queued"
    assert v_r.json()["job"]["kind"] == "voice"

    # 3. Generate project dialogue
    d_r = client.post(f"/api/projects/{pid}/generate-dialogue")
    assert d_r.status_code == 200
    assert d_r.json()["status"] == "queued"
    assert d_r.json()["total_queued"] >= 1


def test_settings_dual_endpoint(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert "comfyui_base_url" in body
    assert "comfyui_audio_base_url" in body

    # Update audio endpoint
    update_r = client.post(
        "/api/settings",
        json={"comfyui_audio_base_url": "http://127.0.0.1:8189"},
    )
    assert update_r.status_code == 200
    assert update_r.json()["comfyui_audio_base_url"] == "http://127.0.0.1:8189"


def test_higgs_emotions_and_hooks():
    from calliope.audio.higgs import enhance_for_higgs, infer_emotion_tags, map_cue_to_higgs_tag

    # Cues
    assert "<|style:whispering|>" in map_cue_to_higgs_tag("whispering")
    assert "<|style:shouting|>" in map_cue_to_higgs_tag("shouting")
    assert "<|sfx:laughter|>" in map_cue_to_higgs_tag("laughing")
    assert "<|emotion:fear|>" in map_cue_to_higgs_tag("panicked")

    # Inferred emotions
    assert "<|style:panicked|>" in infer_emotion_tags("Look out! Run!")
    assert "<|style:laughing|>" in infer_emotion_tags("Haha that is so funny")

    # Enhanced string with hook and prosody
    enhanced = enhance_for_higgs("Don't look back.", cue="whispering", include_hook=True)
    assert enhanced.startswith("[HOOK]")
    assert "<|style:whispering|>" in enhanced
    assert "<|prosody:expressive_high|>" in enhanced
    assert "Don't look back." in enhanced


def test_multispeaker_prompt_and_resolution():
    from calliope.audio.higgs import format_multispeaker_higgs_prompt

    turns = [
        ("ALICE", "whispering", "Do you hear that?"),
        ("BOB", "excited", "Yes, it is amazing!"),
    ]
    prompt, speakers = format_multispeaker_higgs_prompt(turns, include_hook=True)
    assert speakers == ["ALICE", "BOB"]
    assert "[HOOK]" in prompt
    assert "[Speaker_1]:" in prompt
    assert "<|style:whispering|>" in prompt
    assert "[Speaker_2]:" in prompt
    assert "<|style:excited|>" in prompt
