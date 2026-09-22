"""Higgs Audio v3 Voice Cloning & Dialogue TTS Integration.

Targets the dedicated ComfyUI Audio instance (D:\\Backups\\ComfyUI_AD\\ComfyUI)
configured at comfyui_audio_base_url (default: http://127.0.0.1:8189).
Uses Higgs Audio v3 (4B foundation model) with Whisper-large-v3-turbo reference audio transcriber.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from calliope import config
from calliope.comfyui.parser import parse_dynamic_inputs
from calliope.comfyui.smart_fill import smart_fill_inputs
from calliope.db import get_db, row_to_dict
from calliope.queue.manager import queue_manager

import subprocess

logger = logging.getLogger("calliope.audio.higgs")

DEFAULT_MALE_VOICE = "ManVoice42Sec.mp3"
DEFAULT_FEMALE_VOICE = "WomanVoice6Sec.mp3"

SPEAKER_LINE_REGEX = re.compile(
    r"^(?:\[([^\]]+)\]|([A-Za-z0-9_'\s]{1,30}))\s*:\s*(.*)$"
)
CUE_REGEX = re.compile(r"^\s*\(([^)]+)\)\s*(.*)$")


def ensure_clean_audio(path: Path | str | None) -> Path | str | None:
    """Ensure audio file has valid frame headers for PyAV / ComfyUI LoadAudio."""
    if not path:
        return path
    p = Path(path)
    if not p.is_file():
        return path
    if p.suffix.lower() not in (".mp3", ".wav", ".m4a", ".aac", ".flac"):
        return p
    clean_p = p.with_suffix(f".clean{p.suffix}")
    if clean_p.exists() and clean_p.stat().st_mtime >= p.stat().st_mtime and clean_p.stat().st_size > 0:
        return clean_p
    try:
        res = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(p), "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if not res.stderr or "header missing" not in res.stderr.lower():
            return p
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(p), "-c:a", "libmp3lame", "-b:a", "128k", str(clean_p)],
            capture_output=True,
            timeout=10,
        )
        if clean_p.exists() and clean_p.stat().st_size > 0:
            logger.info("Sanitized audio file %s -> %s", p, clean_p)
            return clean_p
    except Exception as e:
        logger.warning("Failed to verify/clean audio %s: %s", p, e)
    return p


def resolve_audio_path(raw_path: str | None) -> Path | str | None:
    """Resolve an audio file path whether absolute, relative to assets_dir, uploads, or ComfyUI input."""
    if not raw_path:
        return None
    raw_str = str(raw_path).strip().replace("\\", "/")

    # Built-in presets in ComfyUI input directory
    if raw_str in (DEFAULT_MALE_VOICE, DEFAULT_FEMALE_VOICE, "WomanVoice9Sec.mp3"):
        comfy_input = Path("D:/Backups/ComfyUI_AD/ComfyUI/input") / raw_str
        if comfy_input.exists():
            return ensure_clean_audio(comfy_input)
        return raw_str

    p = Path(raw_str)
    if p.is_absolute() and p.exists():
        return ensure_clean_audio(p)

    cleaned = raw_str.lstrip("/\\")
    # 1. Under assets_dir (e.g. uploads/xxx.mp3)
    cand = config.settings.assets_dir / cleaned
    if cand.exists():
        return ensure_clean_audio(cand)

    # 2. Under assets_dir / "uploads" / filename
    cand = config.settings.assets_dir / "uploads" / p.name
    if cand.exists():
        return ensure_clean_audio(cand)

    # 3. Under data_dir / cleaned
    cand = config.settings.data_dir / cleaned
    if cand.exists():
        return ensure_clean_audio(cand)

    # 4. Under ComfyUI input
    cand = Path("D:/Backups/ComfyUI_AD/ComfyUI/input") / p.name
    if cand.exists():
        return ensure_clean_audio(cand)

    # 5. Relative to CWD
    if p.exists():
        return ensure_clean_audio(p.resolve())

    return raw_str


def parse_dialogue_line(raw_line: str) -> tuple[str | None, str | None, str]:
    """Parse a script dialogue line into (speaker_name, delivery_cue, spoken_text).
    
    Examples:
        "JOHN: (whispers) Don't look back." -> ("JOHN", "whispers", "Don't look back.")
        "MARY: I hear someone coming." -> ("MARY", None, "I hear someone coming.")
        "Run!" -> (None, None, "Run!")
    """
    line = raw_line.strip()
    speaker: str | None = None
    cue: str | None = None
    spoken: str = line

    m = SPEAKER_LINE_REGEX.match(line)
    if m:
        speaker = (m.group(1) or m.group(2) or "").strip()
        spoken = m.group(3).strip()

    cue_m = CUE_REGEX.match(spoken)
    if cue_m:
        cue = cue_m.group(1).strip()
        spoken = cue_m.group(2).strip()

    return speaker, cue, spoken


CUE_TO_HIGGS: dict[str, str] = {
    # Whispering / soft
    "whisper": "<|style:whispering|>",
    "whispers": "<|style:whispering|>",
    "whispering": "<|style:whispering|>",
    "softly": "<|style:whispering|>",
    "hushed": "<|style:whispering|>",
    "murmur": "<|style:whispering|>",
    "mutter": "<|style:whispering|>",
    "quietly": "<|style:whispering|>",
    # Shouting / loud / screaming
    "shout": "<|style:shouting|>",
    "shouts": "<|style:shouting|>",
    "shouting": "<|style:shouting|>",
    "yell": "<|style:shouting|>",
    "yells": "<|style:shouting|>",
    "yelling": "<|style:shouting|>",
    "scream": "<|style:shouting|>",
    "screams": "<|style:shouting|>",
    "screaming": "<|style:shouting|>",
    "bellow": "<|style:shouting|>",
    "roar": "<|style:shouting|>",
    # Panic / Fear / Nervous
    "panic": "<|style:panicked|><|emotion:fear|>",
    "panicked": "<|style:panicked|><|emotion:fear|>",
    "panicking": "<|style:panicked|><|emotion:fear|>",
    "terrified": "<|style:panicked|><|emotion:fear|>",
    "scared": "<|style:panicked|><|emotion:fear|>",
    "fear": "<|emotion:fear|>",
    "afraid": "<|emotion:fear|>",
    "frantic": "<|style:panicked|><|emotion:fear|>",
    "trembling": "<|style:whispering|><|emotion:fear|>",
    "nervous": "<|emotion:fear|>",
    # Anger / Fierce
    "angry": "<|style:angry|><|emotion:anger|>",
    "furious": "<|style:angry|><|emotion:anger|>",
    "rage": "<|style:angry|><|emotion:anger|>",
    "enraged": "<|style:angry|><|emotion:anger|>",
    "snarl": "<|style:angry|><|emotion:anger|>",
    "growl": "<|style:angry|><|emotion:anger|>",
    "livid": "<|style:angry|><|emotion:anger|>",
    "harsh": "<|style:angry|>",
    # Sadness / Crying / Grief
    "cry": "<|style:crying|><|sfx:crying|>Sob, <|emotion:sadness|>",
    "crying": "<|style:crying|><|sfx:crying|>Sob, <|emotion:sadness|>",
    "sob": "<|style:crying|><|sfx:crying|>Sob, <|emotion:sadness|>",
    "sobbing": "<|style:crying|><|sfx:crying|>Sob, <|emotion:sadness|>",
    "teary": "<|style:crying|><|emotion:sadness|>",
    "weeping": "<|style:crying|><|sfx:crying|>Sob, <|emotion:sadness|>",
    "grief": "<|emotion:sadness|>",
    "mournful": "<|emotion:sadness|>",
    "heartbroken": "<|style:crying|><|emotion:sadness|>",
    # Laughter / Amusement
    "laugh": "<|style:laughing|><|sfx:laughter|>Haha, <|emotion:amusement|>",
    "laughs": "<|style:laughing|><|sfx:laughter|>Haha, <|emotion:amusement|>",
    "laughing": "<|style:laughing|><|sfx:laughter|>Haha, <|emotion:amusement|>",
    "chuckle": "<|style:laughing|><|sfx:laughter|>Haha, ",
    "chuckling": "<|style:laughing|><|sfx:laughter|>Haha, ",
    "giggle": "<|style:laughing|><|sfx:laughter|>Haha, ",
    "snicker": "<|style:laughing|><|sfx:laughter|>Heh, ",
    # Sigh / Relief
    "sigh": "<|sfx:sigh|>Ahh, <|emotion:relief|>",
    "sighing": "<|sfx:sigh|>Ahh, <|emotion:relief|>",
    "relief": "<|emotion:relief|>",
    "relieved": "<|emotion:relief|>",
    # Gasp / Surprise / Shock
    "gasp": "<|sfx:gasp|><|emotion:surprise|>",
    "gasps": "<|sfx:gasp|><|emotion:surprise|>",
    "gasping": "<|sfx:gasp|><|emotion:surprise|>",
    "stunned": "<|sfx:gasp|><|emotion:surprise|>",
    "shocked": "<|sfx:gasp|><|emotion:surprise|>",
    "disbelief": "<|emotion:surprise|>",
    # Vocal SFX
    "cough": "<|sfx:cough|>Ahem, ",
    "ahem": "<|sfx:cough|>Ahem, ",
    "groan": "<|sfx:groan|>Ugh, ",
    "groaning": "<|sfx:groan|>Ugh, ",
    # Excitement / Joy
    "excited": "<|style:excited|><|emotion:elation|>",
    "thrilled": "<|style:excited|><|emotion:elation|>",
    "ecstatic": "<|style:excited|><|emotion:elation|>",
    "cheerful": "<|style:cheerful|><|emotion:elation|>",
    "happy": "<|style:cheerful|><|emotion:elation|>",
    "joy": "<|emotion:elation|>",
    "joyful": "<|style:cheerful|><|emotion:elation|>",
    # Sarcasm / Irony
    "sarcastic": "<|style:sarcastic|>",
    "mocking": "<|style:sarcastic|>",
    "smug": "<|style:sarcastic|>",
    "ironic": "<|style:sarcastic|>",
    # Dramatic / Intense
    "dramatic": "<|style:dramatic|>",
    "intense": "<|style:dramatic|>",
    "solemn": "<|style:dramatic|>",
    "serious": "<|style:dramatic|>",
    "tender": "<|style:cheerful|>",
    "tenderly": "<|style:cheerful|>",
    # Confusion
    "confused": "<|emotion:confusion|>",
    "puzzled": "<|emotion:confusion|>",
    "hesitant": "<|emotion:confusion|>",
}


def map_cue_to_higgs_tag(cue: str | None) -> str:
    """Translate standard script delivery cues into Higgs Audio inline control tags."""
    if not cue:
        return ""
    c = cue.lower().strip()
    # Exact or keyword match
    for key, tag in CUE_TO_HIGGS.items():
        if key in c:
            return tag
    return ""


def infer_emotion_tags(text: str) -> str:
    """Infer emotion, style, and vocalization tags from dialogue content when cue is omitted."""
    lower = text.lower().strip()
    if any(w in lower for w in ("haha", "hehe", "heh", "lol")):
        return "<|style:laughing|><|sfx:laughter|>"
    if any(w in lower for w in ("look out", "run!", "hurry", "get down", "watch out", "help!", "no, no", "oh god", "danger")):
        return "<|style:panicked|><|emotion:fear|>"
    if any(w in lower for w in ("shut up", "damn it", "how dare you", "i swear", "i'll kill", "get out")):
        return "<|style:angry|><|emotion:anger|>"
    if any(w in lower for w in ("i'm sorry", "goodbye", "too late", "she's gone", "he's gone", "lost forever", "forgive me")):
        return "<|style:crying|><|emotion:sadness|>"
    if lower.startswith(("what the", "oh my god", "no way", "how is that possible", "is that")):
        return "<|sfx:gasp|><|emotion:surprise|>"
    if any(w in lower for w in ("thank god", "we made it", "finally", "it's over", "safe now")):
        return "<|sfx:sigh|>Ahh, <|emotion:relief|>"
    if any(w in lower for w in ("we did it", "amazing", "incredible", "awesome", "yes!", "beautiful", "wonderful")):
        return "<|style:excited|><|emotion:elation|>"
    if text.endswith("?") and any(w in lower for w in ("what", "why", "who", "where", "how", "really")):
        return "<|emotion:confusion|>"
    if "!!" in text or "!?" in text:
        return "<|style:excited|>"
    return "<|style:dramatic|>"


def enhance_for_higgs(
    spoken_text: str,
    cue: str | None = None,
    include_hook: bool = True,
) -> str:
    """Enhance spoken dialogue with natural prosody pauses, hooks, and emotional tags for Higgs Audio v3."""
    cleaned = spoken_text.strip()
    # Replace ellipsis and long dashes with prosody pauses
    cleaned = re.sub(r"\.{3,}", " <|prosody:pause|> ", cleaned)
    cleaned = re.sub(r"\s*--+\s*", " <|prosody:pause|> ", cleaned)
    # Natural micro-pause at commas and semicolons
    cleaned = re.sub(r"([,;:])\s+", r"\1 <|prosody:pause|> ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    tag = map_cue_to_higgs_tag(cue)
    if not tag and not any(k in cleaned for k in ("<|style:", "<|emotion:", "<|sfx:")):
        tag = infer_emotion_tags(cleaned)

    # Prepend prosody tag if not already specified
    prefix = ""
    if "<|prosody:" not in tag and "<|prosody:" not in cleaned:
        prefix = "<|prosody:expressive_high|>"

    # Opening hook prefix for energetic Higgs delivery
    hook_tag = ""
    if include_hook and "[HOOK]" not in cleaned:
        hook_tag = "[HOOK] "

    return f"{hook_tag}{prefix}{tag}{cleaned}"


def parse_screenplay_dialogue(text: str | None) -> list[dict[str, Any]]:
    """Parse a screenplay dialogue string into a structured list of dialogue speech turns.
    
    Handles both styles:
    Style A:
        ALICE: (whispering) We have to leave right now.
        BOB: I'm ready.
    Style B (Standard screenplay multi-line layout):
        PUFF
        (wistful)
        I wish I could make big thunder like that.
        
        PUFF
        Oh no... you're so thirsty! I'll try my best.
    """
    if not text:
        return []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    turns: list[dict[str, Any]] = []
    current_speaker: str | None = None
    current_cue: str | None = None
    current_speech: list[str] = []

    for line in lines:
        # Check Style A: 'SPEAKER: (cue) speech' or 'SPEAKER: speech'
        m_inline = re.match(r"^(?:\[([^\]]+)\]|([A-Za-z0-9_'\s]{1,30}))\s*:\s*(.*)$", line)
        if m_inline:
            if current_speech or current_speaker:
                speech_text = " ".join(current_speech).strip()
                if speech_text:
                    turns.append({
                        "speaker": current_speaker,
                        "cue": current_cue,
                        "text": speech_text,
                    })
                current_speech = []
                current_cue = None
            current_speaker = (m_inline.group(1) or m_inline.group(2) or "").strip()
            rest = m_inline.group(3).strip()
            cue_m = re.match(r"^\(([^)]+)\)\s*(.*)$", rest)
            if cue_m:
                current_cue = cue_m.group(1).strip()
                rest = cue_m.group(2).strip()
            if rest:
                current_speech.append(rest)
            continue

        # Check if line is a standalone character name (e.g. 'PUFF' or 'PUFF (V.O.)' or 'ALICE SMITH')
        is_name = (
            line.isupper()
            and len(line.split()) <= 4
            and not line.endswith((".", "!", "?", ",", ";"))
            and not line.startswith("(")
        )
        if is_name:
            if current_speech or current_speaker:
                speech_text = " ".join(current_speech).strip()
                if speech_text:
                    turns.append({
                        "speaker": current_speaker,
                        "cue": current_cue,
                        "text": speech_text,
                    })
                current_speech = []
                current_cue = None
            current_speaker = line
            continue

        # Check if line is a standalone delivery cue in parens: '(wistful)'
        if line.startswith("(") and line.endswith(")"):
            current_cue = line.strip("() ")
            continue

        # Spoken text
        current_speech.append(line)

    if current_speech or current_speaker:
        speech_text = " ".join(current_speech).strip()
        if speech_text:
            turns.append({
                "speaker": current_speaker,
                "cue": current_cue,
                "text": speech_text,
            })

    return turns


def extract_clip_dialogue_turns(scene_dialog: str | None, dialog_lines_covered: Any) -> list[dict[str, Any]]:
    """Resolve clip's dialog_lines_covered to actual spoken turns from scene.dialog."""
    if not scene_dialog:
        return []
    turns = parse_screenplay_dialogue(scene_dialog)
    if not turns:
        return []

    covered_idxs: list[int] = []
    if dialog_lines_covered:
        if isinstance(dialog_lines_covered, str):
            try:
                parsed = json.loads(dialog_lines_covered)
                if isinstance(parsed, list):
                    covered_idxs = [int(x) for x in parsed if str(x).isdigit()]
                elif str(parsed).isdigit():
                    covered_idxs = [int(parsed)]
            except Exception:
                pass
        elif isinstance(dialog_lines_covered, list):
            covered_idxs = [int(x) for x in dialog_lines_covered if str(x).isdigit()]

    if not covered_idxs:
        return turns

    picked = []
    for idx in covered_idxs:
        if 1 <= idx <= len(turns):
            picked.append(turns[idx - 1])

    # If 1-based index fell out of turns range (e.g. was based on raw line numbering),
    # clamp to turn count if only 1 turn exists
    if not picked and len(turns) == 1:
        picked.append(turns[0])

    return picked or turns


def get_clip_dialog_lines(scene_dialog: str | None, dialog_lines_covered: Any) -> list[str]:
    """Resolve 1-based dialog_lines_covered against scene.dialog lines returning clean spoken strings."""
    turns = extract_clip_dialogue_turns(scene_dialog, dialog_lines_covered)
    res = []
    for t in turns:
        spk = t.get("speaker")
        cue = t.get("cue")
        txt = t.get("text", "")
        prefix = f"{spk}: " if spk else ""
        cue_str = f"({cue}) " if cue else ""
        res.append(f"{prefix}{cue_str}{txt}".strip())
    return res


def format_multispeaker_higgs_prompt(
    turns: list[tuple[str | None, str | None, str]],
    include_hook: bool = True,
) -> tuple[str, list[str]]:
    """Format multiple dialogue turns into Higgs multi-speaker prompt.
    
    Returns:
        (formatted_prompt, [speaker_1_name, speaker_2_name])
    """
    speakers: list[str] = []
    for spk, _, _ in turns:
        s_name = (spk or "Speaker").strip()
        if s_name not in speakers and len(speakers) < 2:
            speakers.append(s_name)

    lines: list[str] = []
    for spk, cue, spoken in turns:
        s_name = (spk or "Speaker").strip()
        spk_idx = 1
        if len(speakers) >= 2 and s_name == speakers[1]:
            spk_idx = 2
        enhanced_line = enhance_for_higgs(spoken, cue, include_hook=False)
        lines.append(f"[Speaker_{spk_idx}]: {enhanced_line}")

    prompt_text = "\n".join(lines)
    if include_hook and "[HOOK]" not in prompt_text:
        prompt_text = f"[HOOK]\n\n{prompt_text}"
    return prompt_text, speakers


def resolve_registered_audio_workflow(
    conn: Any,
    *,
    multi_speaker: bool = False,
    has_reference: bool = False,
) -> int | None:
    """Find the best enabled audio workflow from Calliope's workflows table.
    
    1. Multi-speaker: looks for enabled audio workflow matching 'multispeaker'.
    2. Voice clone: looks for enabled audio workflow matching 'reference' or 'clone'.
    3. Direct TTS: looks for enabled audio workflow matching 'only_audio' or 'tts'.
    4. Fallback: first enabled audio workflow.
    """
    if multi_speaker:
        row = conn.execute(
            """
            SELECT id FROM workflows
            WHERE is_enabled = 1 AND kind = 'audio'
              AND (LOWER(name) LIKE '%multispeaker%' OR LOWER(name) LIKE '%multi_speaker%')
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        if row:
            return row["id"]

    if has_reference:
        row = conn.execute(
            """
            SELECT id FROM workflows
            WHERE is_enabled = 1 AND kind = 'audio'
              AND (LOWER(name) LIKE '%reference%' OR LOWER(name) LIKE '%clone%')
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        if row:
            return row["id"]

    row = conn.execute(
        """
        SELECT id FROM workflows
        WHERE is_enabled = 1 AND kind = 'audio'
          AND (LOWER(name) LIKE '%only_audio%' OR LOWER(name) LIKE '%only%' OR LOWER(name) LIKE '%tts%')
        ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    if row:
        return row["id"]

    row = conn.execute(
        "SELECT id FROM workflows WHERE is_enabled = 1 AND kind = 'audio' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def build_higgs_v3_prompt(
    text: str,
    reference_audio_path: str | None = None,
    output_prefix: str = "higgs_voice",
) -> dict[str, Any]:
    """Build ComfyUI prompt graph for Higgs Audio v3.
    
    If reference_audio_path is provided, uses Whisper transcribe + Voice Cloning.
    Otherwise, generates base TTS.
    """
    prompt: dict[str, Any] = {
        "1": {
            "class_type": "HiggsV3LoadModel",
            "inputs": {
                "model": "higgs-audio-v3-tts-4b",
                "dtype": "auto",
                "device": "auto",
                "attention": "auto",
                "download_if_missing": False,
            },
        },
        "44": {
            "class_type": "ttN text",
            "inputs": {"text": text},
        },
    }

    resolved_ref = resolve_audio_path(reference_audio_path)
    if resolved_ref:
        audio_val = str(resolved_ref) if isinstance(resolved_ref, Path) else resolved_ref
        prompt["8"] = {
            "class_type": "LoadAudio",
            "inputs": {"audio": audio_val},
        }
        prompt["5"] = {
            "class_type": "HiggsV3WhisperTranscribe",
            "inputs": {
                "audio": ["8", 0],
                "model": "whisper-large-v3-turbo (auto-download)",
                "dtype": "auto",
                "language": "auto",
                "task": "transcribe",
                "chunk_length_s": 30,
                "download_if_missing": False,
            },
        }
        prompt["35"] = {
            "class_type": "HiggsV3VoiceClone",
            "inputs": {
                "higgs_model": ["1", 0],
                "reference_audio": ["8", 0],
                "text": ["44", 0],
                "reference_text": ["5", 0],
                "max_new_tokens": 2048,
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 50,
                "seed": 42,
                "longform_chunking": True,
                "words_per_chunk": 45,
                "pause_between_chunks": 0.15,
            },
        }
        prompt["9"] = {
            "class_type": "SaveAudioMP3",
            "inputs": {
                "audio": ["35", 0],
                "filename_prefix": output_prefix,
                "quality": "320k",
            },
        }
    else:
        # Fallback to direct Higgs generation if no voice sample
        prompt["35"] = {
            "class_type": "HiggsV3Generate",
            "inputs": {
                "higgs_model": ["1", 0],
                "text": ["44", 0],
                "max_new_tokens": 2048,
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 50,
                "seed": 42,
                "longform_chunking": True,
                "words_per_chunk": 45,
                "pause_between_chunks": 0.15,
            },
        }
        prompt["9"] = {
            "class_type": "SaveAudioMP3",
            "inputs": {
                "audio": ["35", 0],
                "filename_prefix": output_prefix,
                "quality": "320k",
            },
        }

    return prompt


def build_fish_s2_prompt(
    text: str,
    reference_audio_path: str | None = None,
    output_prefix: str = "fish_voice",
    model_variant: str = "s2-pro-fp8",
) -> dict[str, Any]:
    """Build ComfyUI prompt graph for Fish Audio S2 Pro Voice Cloning & TTS."""
    resolved_ref = resolve_audio_path(reference_audio_path)
    if resolved_ref:
        audio_val = str(resolved_ref) if isinstance(resolved_ref, Path) else resolved_ref
        prompt = {
            "8": {
                "class_type": "LoadAudio",
                "inputs": {"audio": audio_val},
            },
            "12": {
                "class_type": "FishS2VoiceCloneTTS",
                "inputs": {
                    "model_path": model_variant,
                    "text": text,
                    "reference_audio": ["8", 0],
                    "language": "auto",
                    "device": "auto",
                    "precision": "auto",
                    "attention": "auto",
                    "keep_model_loaded": True,
                    "offload_to_cpu": False,
                    "compile_model": False,
                },
            },
            "9": {
                "class_type": "SaveAudioMP3",
                "inputs": {
                    "audio": ["12", 0],
                    "filename_prefix": output_prefix,
                    "quality": "320k",
                },
            },
        }
    else:
        prompt = {
            "12": {
                "class_type": "FishS2TTS",
                "inputs": {
                    "model_path": model_variant,
                    "text": text,
                    "language": "auto",
                    "device": "auto",
                    "precision": "auto",
                    "attention": "auto",
                    "keep_model_loaded": True,
                    "offload_to_cpu": False,
                    "compile_model": False,
                },
            },
            "9": {
                "class_type": "SaveAudioMP3",
                "inputs": {
                    "audio": ["12", 0],
                    "filename_prefix": output_prefix,
                    "quality": "320k",
                },
            },
        }
    return prompt


def build_voice_clone_prompt(
    text: str,
    reference_audio_path: str | None = None,
    output_prefix: str = "character_voice",
    engine: str = "higgs",
) -> dict[str, Any]:
    """Dispatch voice cloning / TTS generation to the chosen engine."""
    if engine and engine.lower() in ("fish", "fish_s2", "fishaudio"):
        return build_fish_s2_prompt(text, reference_audio_path, output_prefix=output_prefix)
    return build_higgs_v3_prompt(text, reference_audio_path, output_prefix=output_prefix)


def enqueue_clip_dialog_job(
    project_id: int,
    clip_id: int,
    *,
    text: str | None = None,
    character_id: int | None = None,
    engine: str = "higgs",
    voice_option: str = "reference",  # "reference", "male", "female"
    enhanced: bool = True,
    workflow_id: int | None = None,
) -> dict[str, Any] | None:
    """Queue a voice dialogue generation job for a specific clip.
    
    Supports:
    - Resolving dialog_lines_covered against scene.dialog lines cleanly
    - Filtering out speaker prefixes ('JOHN:') so TTS reads only spoken dialogue
    - Detecting multi-speaker scenes vs single-speaker voice cloning vs direct TTS
    - Dynamic ComfyUI audio workflow resolution from Calliope's database:
      * local_higgs_multispeaker_dialogue_API (multi-speaker turns with Speaker 1 & 2 voices)
      * local_higgs_reference_voice_clone_API (single speaker voice cloning)
      * local_higgs_only_audio_tts_API (direct TTS)
    - Enhanced prosody, hooks ([HOOK]), styles (<|style:...|>), SFX (<|sfx:...|>), and emotions (<|emotion:...|>)
    """
    conn = get_db(config.settings.db_path)
    try:
        clip_row = conn.execute(
            """
            SELECT c.*, s.dialog, s.order_index AS scene_order_index
            FROM clips c JOIN scenes s ON s.id = c.scene_id
            WHERE c.id = ?
            """,
            (clip_id,),
        ).fetchone()
        if not clip_row:
            return None

        clip = row_to_dict(clip_row)
        dialog_text = text

        # If text is numeric or serialized list (legacy bug where index was sent), discard it
        if dialog_text:
            cleaned_check = dialog_text.strip().strip("[]'\"")
            if cleaned_check.isdigit():
                dialog_text = None

        speaker_name: str | None = None
        delivery_cue: str | None = None
        parsed_lines: list[tuple[str | None, str | None, str]] = []

        if not dialog_text:
            raw_lines = get_clip_dialog_lines(clip_row["dialog"], clip.get("dialog_lines_covered"))
            for ln in raw_lines:
                spk, cue, spoken = parse_dialogue_line(ln)
                if not speaker_name and spk:
                    speaker_name = spk
                if not delivery_cue and cue:
                    delivery_cue = cue
                parsed_lines.append((spk, cue, spoken))

        # Determine if this is multi-speaker dialogue
        unique_speakers = list(dict.fromkeys(spk for spk, _, _ in parsed_lines if spk))
        is_multi_speaker = len(unique_speakers) >= 2 and engine.lower() == "higgs"

        speakers_in_prompt: list[str] = []
        ref_audios: list[str] = []

        if is_multi_speaker:
            dialog_text, speakers_in_prompt = format_multispeaker_higgs_prompt(parsed_lines, include_hook=True)
            # Resolve reference voices for Speaker 1 and Speaker 2
            for spk_n in speakers_in_prompt[:2]:
                c_row = conn.execute(
                    "SELECT id, name, voice_sample_path, appearance FROM characters WHERE project_id = ? AND LOWER(name) = ? LIMIT 1",
                    (project_id, spk_n.lower()),
                ).fetchone()
                if not c_row:
                    c_row = conn.execute(
                        "SELECT id, name, voice_sample_path, appearance FROM characters WHERE project_id = ? AND LOWER(name) LIKE ? LIMIT 1",
                        (project_id, f"%{spk_n.lower()}%"),
                    ).fetchone()
                
                v_sample: str | None = None
                if c_row and c_row["voice_sample_path"]:
                    v_sample = c_row["voice_sample_path"]
                else:
                    desc = f" {c_row['name'] if c_row else spk_n} {c_row['appearance'] if c_row else ''} ".lower()
                    if any(w in desc for w in (" male", " man", " boy", " father", " guy", " brother", " son", " king", " prince")):
                        v_sample = DEFAULT_MALE_VOICE
                    else:
                        v_sample = DEFAULT_FEMALE_VOICE
                ref_audios.append(v_sample)
            primary_voice_sample = ref_audios[0] if ref_audios else None
            target_char_id = None
        else:
            if not dialog_text:
                if parsed_lines:
                    if enhanced and engine.lower() == "higgs":
                        dialog_text = " <|prosody:pause|> ".join(
                            enhance_for_higgs(spk, c, include_hook=True) for _, c, spk in parsed_lines
                        )
                    else:
                        dialog_text = " ".join(spk for _, _, spk in parsed_lines)

                if not dialog_text:
                    dialog_text = clip.get("description") or clip_row["dialog"] or ""

            dialog_text = dialog_text.strip()
            if not dialog_text:
                logger.info("Clip %s has no dialog lines; skipping audio generation", clip_id)
                return None

            # Resolve target character
            char_row = None
            target_char_id = character_id
            if target_char_id:
                char_row = conn.execute(
                    "SELECT id, name, voice_sample_path, appearance FROM characters WHERE id = ?",
                    (target_char_id,),
                ).fetchone()
            elif speaker_name:
                char_row = conn.execute(
                    "SELECT id, name, voice_sample_path, appearance FROM characters WHERE project_id = ? AND LOWER(name) = ? LIMIT 1",
                    (project_id, speaker_name.lower()),
                ).fetchone()
                if not char_row:
                    char_row = conn.execute(
                        "SELECT id, name, voice_sample_path, appearance FROM characters WHERE project_id = ? AND LOWER(name) LIKE ? LIMIT 1",
                        (project_id, f"%{speaker_name.lower()}%"),
                    ).fetchone()
                if char_row:
                    target_char_id = char_row["id"]

            if not char_row and not target_char_id:
                char_row = conn.execute(
                    """
                    SELECT c.id, c.name, c.voice_sample_path, c.appearance FROM characters c
                    JOIN scene_characters sc ON sc.character_id = c.id
                    WHERE sc.scene_id = ?
                    ORDER BY c.voice_sample_path IS NOT NULL DESC
                    LIMIT 1
                    """,
                    (clip["scene_id"],),
                ).fetchone()
                if char_row:
                    target_char_id = char_row["id"]

            primary_voice_sample: str | None = None
            if voice_option == "male":
                primary_voice_sample = DEFAULT_MALE_VOICE
            elif voice_option == "female":
                primary_voice_sample = DEFAULT_FEMALE_VOICE
            else:
                if char_row and char_row["voice_sample_path"]:
                    primary_voice_sample = char_row["voice_sample_path"]
                else:
                    desc = f" {char_row['name'] if char_row else ''} {char_row['appearance'] if char_row else ''} ".lower()
                    if any(w in desc for w in (" male", " man", " boy", " father", " guy", " brother", " son", " king", " prince")):
                        primary_voice_sample = DEFAULT_MALE_VOICE
                    else:
                        primary_voice_sample = DEFAULT_FEMALE_VOICE

            if primary_voice_sample:
                ref_audios = [primary_voice_sample]

        # Resolve registered audio workflow if available
        resolved_wf_id = workflow_id or resolve_registered_audio_workflow(
            conn,
            multi_speaker=is_multi_speaker,
            has_reference=bool(primary_voice_sample),
        )

        input_values: dict[str, Any] = {
            "text": dialog_text,
            "reference_audio": primary_voice_sample,
        }

        # If a registered workflow was resolved, smart-fill its dynamic inputs
        if resolved_wf_id:
            wf_row = conn.execute(
                "SELECT workflow_json FROM workflows WHERE id = ?", (resolved_wf_id,)
            ).fetchone()
            if wf_row:
                try:
                    wf_data = json.loads(wf_row["workflow_json"])
                    dyn_inputs = parse_dynamic_inputs(wf_data)
                    filled = smart_fill_inputs(dyn_inputs, prompt=dialog_text, ref_audios=ref_audios)
                    if filled:
                        input_values = filled
                except Exception as ex:
                    logger.warning("Failed to smart-fill audio workflow %s: %s", resolved_wf_id, ex)

        payload = {
            "audio_endpoint": True,
            "engine": engine,
            "workflow_id": resolved_wf_id,
            "clip_id": clip_id,
            "character_id": target_char_id,
            "voice_option": voice_option,
            "enhanced": enhanced,
            "multi_speaker": is_multi_speaker,
            "dialog_text": dialog_text,
            "voice_sample_path": primary_voice_sample,
            "ref_audios": ref_audios,
            "input_values": input_values,
        }

        job = queue_manager.enqueue(
            project_id=project_id,
            kind="voice",
            workflow_id=resolved_wf_id,
            scene_id=clip["scene_id"],
            clip_id=clip_id,
            payload=payload,
        )
        conn.commit()
        return job
    finally:
        conn.close()
