"""Folder watcher: Watchdog observer -> enqueue jobs into the pipeline.

We debounce "settle" seconds after the last write so we never read a
half-finished file.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import get_config
from .pipeline import get_pipeline


class _Handler(FileSystemEventHandler):
    def __init__(self, settle_seconds: float, extensions, enqueue):
        self.settle_seconds = settle_seconds
        self.extensions = tuple(e.lower() for e in extensions)
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self.enqueue = enqueue

    def _matches(self, path: str) -> bool:
        return path.lower().endswith(self.extensions)

    def _schedule(self, path: str) -> None:
        with self._lock:
            t = self._timers.pop(path, None)
            if t is not None:
                t.cancel()
            timer = threading.Timer(self.settle_seconds, self._fire, args=(path,))
            self._timers[path] = timer
            timer.daemon = True
            timer.start()

    def _fire(self, path: str) -> None:
        with self._lock:
            self._timers.pop(path, None)
        if not os.path.exists(path):
            return
        if not self._matches(path):
            return
        # Skip zero-byte files.
        try:
            if os.path.getsize(path) == 0:
                return
        except OSError:
            return
        self.enqueue(path)

    def on_created(self, event):
        if event.is_directory:
            return
        self._schedule(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        self._schedule(event.dest_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._schedule(event.src_path)


class Watcher:
    def __init__(self) -> None:
        self.cfg = get_config()
        self.observer: Optional[Observer] = None
        self._thread: Optional[threading.Thread] = None
        self._job_lock = threading.Lock()
        self._active = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._active.is_set()

    def enqueue(self, path: str) -> None:
        """Run a pipeline job in a background thread."""
        def _run():
            with self._job_lock:
                try:
                    get_pipeline().process_file(path)
                except Exception as e:
                    print(f"[watcher] job failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def start(self) -> bool:
        if self._active.is_set():
            return True
        folder = self.cfg.get("paths.watch_folder", "./watch")
        Path(folder).mkdir(parents=True, exist_ok=True)
        settle = float(self.cfg.get("watcher.settle_seconds", 2))
        exts = list(self.cfg.get("watcher.extensions", [".wav"]))

        handler = _Handler(settle, exts, self.enqueue)
        self.observer = Observer()
        self.observer.schedule(handler, folder, recursive=False)
        self.observer.daemon = True
        self.observer.start()
        self._active.set()
        print(f"[watcher] watching {os.path.abspath(folder)} for {exts}")
        return True

    def stop(self) -> bool:
        if not self._active.is_set():
            return True
        try:
            if self.observer is not None:
                self.observer.stop()
                self.observer.join(timeout=2)
        except Exception:
            pass
        self.observer = None
        self._active.clear()
        print("[watcher] stopped")
        return True


_watcher_singleton: Optional[Watcher] = None


def get_watcher() -> Watcher:
    global _watcher_singleton
    if _watcher_singleton is None:
        _watcher_singleton = Watcher()
    return _watcher_singleton
