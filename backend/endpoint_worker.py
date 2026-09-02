"""Isolated endpoint scan used to keep the local web server responsive."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .architecture_detector import detect_architecture
from .java_parser import endpoints, parse_project


def main() -> int:
    started = time.perf_counter()
    project = Path(sys.argv[1]).resolve()
    print(f"endpoint-scan start project={project}", file=sys.stderr, flush=True)
    try:
        types = parse_project(project)
        result = {
            "project": str(project),
            "endpoints": endpoints(types),
            "architecture": detect_architecture(types),
            "java_types": len(types),
        }
        print(json.dumps(result, ensure_ascii=True), flush=True)
        print(
            f"endpoint-scan complete java_types={len(types)} elapsed_ms={(time.perf_counter() - started) * 1000:.0f}",
            file=sys.stderr,
            flush=True,
        )
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), flush=True)
        print(f"endpoint-scan failed type={type(exc).__name__} error={exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
