"""FastAPI app: REST + WebSocket + static UI."""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Any, Dict, List

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ws
from .config import get_config
from .db import get_db
from .pipeline import get_pipeline
from .translators import list_translators
from .tts import list_engines
from .watcher import get_watcher


def _language_meta(codes: List[str]) -> List[Dict[str, str]]:
    """Show codes with a friendly English name where known."""
    names = {
        "en": "English", "es": "Spanish", "fr": "French", "de": "German",
        "it": "Italian", "pt": "Portuguese", "ru": "Russian", "zh": "Chinese",
        "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "hi": "Hindi",
        "tr": "Turkish", "nl": "Dutch", "pl": "Polish", "cs": "Czech",
        "hu": "Hungarian", "sv": "Swedish", "fi": "Finnish", "da": "Danish",
        "no": "Norwegian", "el": "Greek", "he": "Hebrew", "id": "Indonesian",
        "ms": "Malay", "vi": "Vietnamese", "th": "Thai", "uk": "Ukrainian",
        "ro": "Romanian", "bg": "Bulgarian", "sk": "Slovak", "hr": "Croatian",
        "fa": "Persian", "bn": "Bengali", "ta": "Tamil", "ur": "Urdu",
        "fil": "Filipino", "sw": "Swahili", "te": "Telugu", "ml": "Malayalam",
        "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "or": "Odia",
        "pa": "Punjabi", "hi-IN": "Hindi (India)", "en-IN": "English (Indian)",
        "as": "Assamese", "brx": "Bodo", "doi": "Dogri", "kok": "Konkani",
        "mai": "Maithili", "mni": "Manipuri", "ne": "Nepali", "sa": "Sanskrit",
        "sat": "Santali", "sd": "Sindhi",
    }
    return [{"code": c, "name": names.get(c, c.upper())} for c in codes]


def create_app() -> FastAPI:
    cfg = get_config()
    cfg.ensure_paths()
    app = FastAPI(title="Audio Translator v1")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Capture the running loop so the worker thread can broadcast.
    @app.on_event("startup")
    async def _on_start():
        ws.set_loop(asyncio.get_running_loop())
        if cfg.get("watcher.auto_start", False):
            get_watcher().start()

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------
    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------
    @app.get("/api/engines")
    def get_engines():
        return {"engines": list_engines(), "enabled": cfg.get("tts.enabled", [])}

    @app.get("/api/translators")
    def get_translators():
        return {
            "translators": list_translators(),
            "default": cfg.get("translator.default", "nllb_local"),
        }

    @app.get("/api/languages")
    def get_languages():
        # Show the union of: configured languages × each engine's supported set.
        engines = list_engines()
        union = set()
        per_engine: Dict[str, List[str]] = {}
        # We need the engine instances to call supported_languages(), but the
        # registry's list_engines() doesn't run that. Build a lightweight lookup
        # by importing each engine module and reading the class attribute.
        from .tts import _REGISTRY
        from .translators import _REGISTRY as T_REG
        for eid, cls in _REGISTRY.items():
            try:
                inst = cls(cfg)
                langs = inst.supported_languages() or []
                per_engine[eid] = langs
                union.update(langs)
                inst.close()
            except Exception:
                per_engine[eid] = []
        configured = list(cfg.get("languages", []))
        # Show the user every language we know about so the UI can offer them.
        all_known = sorted(union | set(configured))
        return {
            "languages": _language_meta(all_known),
            "configured": configured,
            "per_engine": per_engine,
        }

    @app.get("/api/settings")
    def get_settings():
        return {
            "watch_folder": cfg.get("paths.watch_folder"),
            "output_folder": cfg.get("paths.output_folder"),
            "watcher_running": get_watcher().is_running,
            "translator_default": cfg.get("translator.default"),
            "tts_enabled": cfg.get("tts.enabled", []),
            "languages": cfg.get("languages", []),
        }

    @app.post("/api/settings")
    async def post_settings(payload: Dict[str, Any]):
        if "languages" in payload:
            cfg.set("languages", list(payload["languages"]))
        if "tts_enabled" in payload:
            cfg.set("tts.enabled", list(payload["tts_enabled"]))
        if "translator_default" in payload:
            cfg.set("translator.default", str(payload["translator_default"]))
        cfg.save()
        return {"ok": True}

    # ------------------------------------------------------------------
    # Watcher control
    # ------------------------------------------------------------------
    @app.post("/api/watcher/start")
    def watcher_start():
        get_watcher().start()
        return {"running": True}

    @app.post("/api/watcher/stop")
    def watcher_stop():
        get_watcher().stop()
        return {"running": False}

    @app.post("/api/watcher/process")
    async def watcher_process(file: UploadFile):
        """Manually push a file into the pipeline (works even with watcher off)."""
        cfg.ensure_paths()
        watch = Path(cfg.get("paths.watch_folder", "./watch"))
        watch.mkdir(parents=True, exist_ok=True)
        dest = watch / file.filename
        data = await file.read()
        with open(dest, "wb") as f:
            f.write(data)
        # Process in a background thread to keep the request snappy.
        threading.Thread(
            target=get_pipeline().process_file,
            args=(str(dest),),
            daemon=True,
        ).start()
        return {"queued": str(dest)}

    @app.post("/api/process_path")
    def process_existing_path(payload: Dict[str, Any]):
        path = payload.get("path", "").strip()
        if not path or not os.path.exists(path):
            raise HTTPException(404, f"File not found: {path}")
        threading.Thread(
            target=get_pipeline().process_file,
            args=(path,),
            daemon=True,
        ).start()
        return {"queued": path}

    # ------------------------------------------------------------------
    # Jobs / artifacts
    # ------------------------------------------------------------------
    @app.get("/api/jobs")
    def list_jobs(limit: int = 50):
        return {"jobs": get_db().list_jobs(limit=limit)}

    @app.get("/api/jobs/{job_uuid}")
    def get_job(job_uuid: str):
        j = get_db().get_job(job_uuid)
        if not j:
            raise HTTPException(404, "job not found")
        return j

    @app.get("/api/playback")
    def playback_queue(limit: int = 200):
        return {"items": get_db().list_artifacts_for_playback(limit=limit)}

    # ------------------------------------------------------------------
    # Audio streaming
    # ------------------------------------------------------------------
    @app.get("/api/audio")
    def serve_audio(path: str):
        if not os.path.exists(path):
            raise HTTPException(404, "audio not found")
        # Basic safety: only serve from output folder.
        out_dir = os.path.abspath(cfg.get("paths.output_folder", "./outputs"))
        ap = os.path.abspath(path)
        if not ap.startswith(out_dir):
            raise HTTPException(403, "refused")
        return FileResponse(ap, media_type="audio/wav")

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await ws.register(websocket)
        try:
            # Send a hello with current state.
            await websocket.send_json({
                "type": "hello",
                "watcher_running": get_watcher().is_running,
                "settings": {
                    "watch_folder": cfg.get("paths.watch_folder"),
                    "output_folder": cfg.get("paths.output_folder"),
                    "tts_enabled": cfg.get("tts.enabled", []),
                    "languages": cfg.get("languages", []),
                    "translator_default": cfg.get("translator.default"),
                },
            })
            while True:
                # Keep the connection open; we don't need client messages.
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            ws.unregister(websocket)

    return app


# uvicorn entrypoint: `uvicorn app.main:app --reload`
app = create_app()
