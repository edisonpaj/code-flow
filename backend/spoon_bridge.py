"""Safe, optional bridge to the isolated Java/Spoon analyzer.

Spoon runs in shadow mode: its evidence is attached to the response while the
existing Python flow remains authoritative. Missing Java, JARs, timeouts and
invalid output never prevent the legacy analysis from completing.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPOON_JAR = ROOT / "spoon-analyzer" / "target" / "expert-code-flow-spoon.jar"
CACHE = ROOT / ".cache" / "spoon"


def _fingerprint(project: Path) -> str:
    digest = hashlib.sha256(str(project).encode("utf-8"))
    if SPOON_JAR.is_file():
        digest.update(str(SPOON_JAR.stat().st_mtime_ns).encode("ascii"))
    count = 0
    latest = 0
    for source in project.rglob("*.java"):
        if any(part in {"target", "build", ".git"} for part in source.parts):
            continue
        try:
            stat = source.stat()
        except OSError:
            continue
        count += 1
        latest = max(latest, stat.st_mtime_ns)
    bytecode_count = 0
    bytecode_latest = 0
    for compiled in project.rglob("*.class"):
        if any(part in {".git", ".gradle"} for part in compiled.parts):
            continue
        try:
            stat = compiled.stat()
        except OSError:
            continue
        bytecode_count += 1
        bytecode_latest = max(bytecode_latest, stat.st_mtime_ns)
    digest.update(f"{count}:{latest}".encode("ascii"))
    digest.update(f"{bytecode_count}:{bytecode_latest}".encode("ascii"))
    return digest.hexdigest()[:24]


def engine_status() -> dict:
    mode = os.getenv("EXPERT_CODE_FLOW_SPOON", "selectable").strip().lower()
    enabled = mode not in {"0", "false", "off", "disabled"}
    return {"id": "spoon", "mode": mode, "enabled": enabled,
            "available": SPOON_JAR.is_file(), "jar": str(SPOON_JAR),
            "label": "Spoon + SootUp", "capabilities": ["source-ast", "spring-metadata",
                "bytecode", "type-hierarchy", "call-graph-cha", "control-flow"]}


def analyze_with_spoon(project_value: str, timeout_seconds: int = 120, requested: bool = True) -> dict:
    status = engine_status()
    started = time.perf_counter()
    if not requested:
        return {**status, "state": "not_requested", "authoritative": False}
    if not status["enabled"]:
        return {**status, "state": "disabled", "authoritative": False}
    if not status["available"]:
        return {**status, "state": "unavailable", "authoritative": False,
                "message": "JAR do Spoon ainda não foi compilado"}

    project = Path(project_value).resolve()
    cache_file = CACHE / f"{_fingerprint(project)}.json"
    try:
        if cache_file.is_file():
            report = json.loads(cache_file.read_text(encoding="utf-8"))
            return {**status, "state": "ready", "authoritative": False, "cache_hit": True,
                    "duration_ms": round((time.perf_counter() - started) * 1000), "report": report}
        CACHE.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["java", "-jar", str(SPOON_JAR), str(project), str(cache_file)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=timeout_seconds,
            encoding="utf-8", errors="replace", check=False,
        )
        if completed.returncode != 0:
            return {**status, "state": "failed", "authoritative": False,
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                    "message": (completed.stderr or completed.stdout or "Falha no Spoon")[-2000:]}
        report = json.loads(cache_file.read_text(encoding="utf-8"))
        if report.get("schema_version") != "1.0" or report.get("engine") not in {"spoon", "spoon-sootup"}:
            raise ValueError("Contrato JSON do Spoon incompatível")
        return {**status, "state": "ready", "authoritative": False, "cache_hit": False,
                "duration_ms": round((time.perf_counter() - started) * 1000), "report": report}
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {**status, "state": "failed", "authoritative": False,
                "duration_ms": round((time.perf_counter() - started) * 1000), "message": str(exc)}
