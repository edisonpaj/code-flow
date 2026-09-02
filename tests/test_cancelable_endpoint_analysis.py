import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
APP_SCRIPT = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_frontend_endpoint_scan_is_cancelable_and_swagger_is_disabled():
    assert "new AbortController()" in APP_SCRIPT
    assert "/api/analysis/cancel?analysis_id=" in APP_SCRIPT
    assert "timeoutMs:125000" in APP_SCRIPT
    assert "setTimeout(autoLoadRoot,650)" not in APP_SCRIPT
    assert "Promise.all([json('/api/endpoints" not in APP_SCRIPT
    assert 'id="cancel-load"' in INDEX_HTML
    assert "Swagger desativado" in INDEX_HTML


def test_endpoint_worker_returns_json_without_windows_encoding_dependency(tmp_path):
    source = tmp_path / "src" / "main" / "java" / "exemplo"
    source.mkdir(parents=True)
    (source / "SaudacaoController.java").write_text(
        """
        package exemplo;
        @RestController
        @RequestMapping("/saudacoes")
        public class SaudacaoController {
            @GetMapping("/{nome}")
            public String buscar(String nome) { return nome; }
        }
        """,
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, "-m", "backend.endpoint_worker", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout.decode("ascii"))
    assert payload["java_types"] == 1
    assert payload["endpoints"][0]["path"] == "/saudacoes/{nome}"
