from __future__ import annotations

import io
import shutil
import stat
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath


MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024
MAX_ENTRIES = 20_000
UPLOAD_TTL_SECONDS = 24 * 60 * 60


def cleanup_uploads(upload_root: Path) -> None:
    if not upload_root.exists():
        return
    threshold = time.time() - UPLOAD_TTL_SECONDS
    for child in upload_root.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < threshold:
                shutil.rmtree(child)
        except OSError:
            continue


def _safe_member_path(name: str) -> Path:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
        raise ValueError(f"Caminho inseguro no ZIP: {name}")
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts:
        raise ValueError("Entrada vazia encontrada no ZIP")
    return Path(*parts)


def extract_project_zip(data: bytes, filename: str, upload_root: Path) -> Path:
    if not filename.lower().endswith(".zip"):
        raise ValueError("Selecione um arquivo com extensão .zip")
    if not data:
        raise ValueError("O pacote ZIP está vazio")
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("O pacote ZIP excede o limite de 300 MB")
    return _extract_project_zip(io.BytesIO(data), filename, upload_root)


def extract_project_zip_file(archive_path: Path, filename: str, upload_root: Path) -> Path:
    if not archive_path.is_file():
        raise ValueError("O pacote ZIP temporário não foi encontrado")
    size = archive_path.stat().st_size
    if size <= 0:
        raise ValueError("O pacote ZIP está vazio")
    if size > MAX_ARCHIVE_BYTES:
        raise ValueError("O pacote ZIP excede o limite de 300 MB")
    return _extract_project_zip(archive_path, filename, upload_root)


def _extract_project_zip(source: io.BytesIO | Path, filename: str, upload_root: Path) -> Path:
    if not filename.lower().endswith(".zip"):
        raise ValueError("Selecione um arquivo com extensão .zip")
    cleanup_uploads(upload_root)
    target = upload_root / uuid.uuid4().hex
    try:
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > MAX_ENTRIES:
                raise ValueError("O pacote ZIP possui arquivos demais")
            total_size = sum(member.file_size for member in members)
            if total_size > MAX_EXTRACTED_BYTES:
                raise ValueError("O conteúdo extraído excede o limite de 1 GB")
            validated: list[tuple[zipfile.ZipInfo, Path]] = []
            for member in members:
                relative = _safe_member_path(member.filename)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError("Links simbólicos não são permitidos no pacote ZIP")
                if member.flag_bits & 0x1:
                    raise ValueError("Arquivos ZIP criptografados não são suportados")
                validated.append((member, relative))
            target.mkdir(parents=True, exist_ok=False)
            resolved_target = target.resolve()
            for member, relative in validated:
                destination = (target / relative).resolve()
                if resolved_target not in destination.parents and destination != resolved_target:
                    raise ValueError(f"Caminho inseguro no ZIP: {member.filename}")
                if member.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
        return target.resolve()
    except zipfile.BadZipFile as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise ValueError("O arquivo enviado não é um ZIP válido") from exc
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
