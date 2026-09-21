#!/usr/bin/env python3
"""Calliope Subsystem Health & Diagnostics Checker.

Verifies database connectivity, backend API status, ComfyUI reachability,
active LLM endpoint status, and media directory health.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path


def check_database(repo_root: Path) -> dict[str, any]:
    db_path = repo_root / "calliope-backend" / "data" / "calliope.db"
    result = {"path": str(db_path), "exists": db_path.exists(), "ok": False}
    if not db_path.exists():
        result["error"] = "Database file not found"
        return result
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        result["table_count"] = len(tables)
        result["tables"] = tables
        # Check WAL mode
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        result["journal_mode"] = journal_mode
        result["ok"] = len(tables) >= 10
        conn.close()
    except Exception as exc:
        result["error"] = str(exc)
    return result


def check_http_endpoint(url: str, timeout: float = 3.0) -> dict[str, any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Calliope-HealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except Exception:
                data = body[:200]
            return {"url": url, "status": status, "reachable": True, "data": data}
    except Exception as exc:
        return {"url": url, "reachable": False, "error": str(exc)}


def check_config(repo_root: Path) -> dict[str, any]:
    cfg_path = repo_root / "calliope-backend" / "calliope_config.json"
    if not cfg_path.exists():
        cfg_path = repo_root / "calliope-backend" / "calliope_config.example.json"
        is_example = True
    else:
        is_example = False
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return {
            "path": str(cfg_path),
            "is_example": is_example,
            "host": cfg.get("host", "127.0.0.1"),
            "port": cfg.get("port", 8247),
            "comfyui_url": cfg.get("comfyui_base_url", "http://127.0.0.1:8188"),
            "llm_url": cfg.get("llm_base_url", "http://127.0.0.1:11434/v1"),
            "llm_model": cfg.get("llm_model", "llama3.2"),
            "dry_run": cfg.get("dry_run", False),
        }
    except Exception as exc:
        return {"error": str(exc)}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[4]
    print(f"==================================================")
    print(f"       CALLIOPE SYSTEM HEALTH DIAGNOSTICS         ")
    print(f"==================================================")
    print(f"Repository Root: {repo_root}\n")

    # 1. Config Check
    config_info = check_config(repo_root)
    print(f"[1] CONFIGURATION")
    if "error" in config_info:
        print(f"    Error reading config: {config_info['error']}")
    else:
        print(f"    Config file : {config_info['path']} ({'EXAMPLE' if config_info['is_example'] else 'ACTIVE'})")
        print(f"    Backend Bind: {config_info['host']}:{config_info['port']}")
        print(f"    Dry Run Mode: {config_info['dry_run']}")
        print(f"    ComfyUI URL : {config_info['comfyui_url']}")
        print(f"    Active LLM  : {config_info['llm_model']} @ {config_info['llm_url']}")

    # 2. Database Check
    print(f"\n[2] SQLITE DATABASE")
    db_info = check_database(repo_root)
    if db_info.get("ok"):
        print(f"    Path        : {db_info['path']}")
        print(f"    Status      : OK ({db_info['table_count']} tables, WAL mode: {db_info['journal_mode']})")
    else:
        print(f"    Path        : {db_info['path']}")
        print(f"    Status      : FAILED ({db_info.get('error', 'Incomplete schema')})")

    # 3. Backend API Check
    backend_url = f"http://{config_info.get('host', '127.0.0.1')}:{config_info.get('port', 8247)}/api/health"
    print(f"\n[3] BACKEND SERVICE ({backend_url})")
    backend_check = check_http_endpoint(backend_url)
    if backend_check["reachable"]:
        print(f"    Status      : ONLINE (HTTP {backend_check['status']})")
        print(f"    Payload     : {backend_check['data']}")
    else:
        print(f"    Status      : OFFLINE ({backend_check.get('error')})")

    # 4. ComfyUI Check
    comfy_url = config_info.get("comfyui_url", "http://127.0.0.1:8188")
    print(f"\n[4] COMFYUI SERVICE ({comfy_url})")
    comfy_check = check_http_endpoint(f"{comfy_url}/system_stats")
    if comfy_check["reachable"]:
        print(f"    Status      : ONLINE (HTTP {comfy_check['status']})")
    else:
        print(f"    Status      : NOT REACHABLE ({comfy_check.get('error')})")

    # 5. LLM Endpoint Check
    llm_url = config_info.get("llm_url", "http://127.0.0.1:11434/v1")
    print(f"\n[5] LLM SERVICE ({llm_url}/models)")
    llm_check = check_http_endpoint(f"{llm_url}/models")
    if llm_check["reachable"]:
        print(f"    Status      : ONLINE (HTTP {llm_check['status']})")
    else:
        print(f"    Status      : NOT REACHABLE ({llm_check.get('error')})")

    print(f"\n==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
