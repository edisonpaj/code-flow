from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class MaturityCache:
    """Small, portable, file-backed cache for the latest maturity report per project."""

    def __init__(self, root: Path):
        self.root = root
        self._lock = Lock()

    @staticmethod
    def _key(project_path: str) -> str:
        normalized = str(Path(project_path).resolve()).lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]

    def _read(self, path: Path):
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def save(self, report: dict) -> dict:
        context = report.get("context") or {}
        project_path = context.get("project_path")
        if not project_path:
            raise ValueError("O contexto do relatório não contém project_path")
        cached = {**report, "cached_at": datetime.now(timezone.utc).isoformat(),
                  "cache_version": "1.0", "project_key": self._key(project_path)}
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{cached['project_key']}.json"
        latest = self.root / "latest.json"
        with self._lock:
            target.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
            latest.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"cached": True, "project_key": cached["project_key"],
                "cached_at": cached["cached_at"]}

    def latest(self, project_path: str | None = None):
        target = self.root / f"{self._key(project_path)}.json" if project_path else self.root / "latest.json"
        return self._read(target)
