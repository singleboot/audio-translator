"""Entry point: `python run.py`"""

from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from app.config import get_config


def main() -> int:
    cfg = get_config()
    host = cfg.get("server.host", "127.0.0.1")
    port = int(cfg.get("server.port", 8000))

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=host)
    ap.add_argument("--port", type=int, default=port)
    ap.add_argument("--reload", action="store_true", help="dev auto-reload")
    args = ap.parse_args()

    # Make relative paths in config resolve from the cwd at launch.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    cfg.ensure_paths()

    print(f"Starting Audio Translator v1 on http://{args.host}:{args.port}")
    print(f"http://{args.host}:{args.port}")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
