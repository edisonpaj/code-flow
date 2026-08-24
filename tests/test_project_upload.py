import io
import zipfile
from pathlib import Path

import pytest

from backend.project_discovery import discover_projects
from backend.project_upload import extract_project_zip


def make_zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_upload_extracts_and_reuses_spring_project_discovery(tmp_path: Path):
    payload = make_zip({
        "pedido-service/pom.xml": "<project><artifactId>spring-boot-starter-web</artifactId></project>",
        "pedido-service/src/main/java/Pedido.java": "class Pedido {}",
    })
    root = extract_project_zip(payload, "pedido-service.zip", tmp_path / "uploads")
    projects = discover_projects(str(root))
    assert [project["name"] for project in projects] == ["pedido-service"]
    assert Path(projects[0]["path"], "pom.xml").is_file()


def test_upload_rejects_zip_path_traversal(tmp_path: Path):
    payload = make_zip({"../outside.txt": "blocked"})
    with pytest.raises(ValueError, match="Caminho inseguro"):
        extract_project_zip(payload, "unsafe.zip", tmp_path / "uploads")
    assert not (tmp_path / "outside.txt").exists()


def test_upload_rejects_non_zip_extension(tmp_path: Path):
    with pytest.raises(ValueError, match="extensão .zip"):
        extract_project_zip(b"not-a-zip", "project.jar", tmp_path / "uploads")

