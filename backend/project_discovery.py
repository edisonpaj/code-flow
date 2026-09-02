from pathlib import Path
import os
import re


IGNORED = {".git", ".gradle", ".idea", ".mvn", ".settings", ".vscode", "build", "dist", "node_modules", "out", "target"}


def is_spring_project(path: Path) -> bool:
    pom = path / "pom.xml"
    gradle = path / "build.gradle"
    gradle_kts = path / "build.gradle.kts"
    files = [p for p in (pom, gradle, gradle_kts) if p.exists()]
    if not files:
        return False
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in files)
    return "spring-boot" in text or "org.springframework" in text


def discover_projects(root_value: str) -> list[dict]:
    normalized = root_value.strip()
    if os.name == "nt" and re.fullmatch(r"[A-Za-z]:", normalized):
        normalized += "\\"
    root = Path(normalized).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Diretório não encontrado: {root}")
    if is_spring_project(root):
        return [{"name": root.name, "path": str(root)}]
    found = []
    for current, dirnames, _ in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in IGNORED]
        path = Path(current)
        if path != root and is_spring_project(path):
            found.append({"name": path.name, "path": str(path)})
            dirnames[:] = []
    return sorted(found, key=lambda item: (len(Path(item["path"]).parts), item["name"]))


def _resolved_value(value: str, fallback: str) -> str:
    value = value.strip().strip('"\'')
    placeholder = re.fullmatch(r"\$\{[^:}]+(?::([^}]+))?}", value)
    return (placeholder.group(1) if placeholder and placeholder.group(1) else fallback) if placeholder else value


def swagger_info(project_value: str) -> dict:
    project = Path(project_value).resolve()
    if not project.is_dir(): raise ValueError("Projeto não encontrado")
    build_files = [p for p in (project / "pom.xml", project / "build.gradle", project / "build.gradle.kts") if p.exists()]
    build_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in build_files)
    detected = "springdoc" in build_text.lower() or "swagger" in build_text.lower()
    port, context_path, swagger_path = "8080", "", "/swagger-ui/index.html"
    resources = project / "src/main/resources"
    configs = [] if not resources.exists() else list(resources.glob("application*.properties")) + list(resources.glob("application*.yml")) + list(resources.glob("application*.yaml"))
    for config in configs:
        text = config.read_text(encoding="utf-8", errors="ignore")
        flat_port = re.search(r"(?m)^\s*server\.port\s*=\s*([^#\r\n]+)", text)
        yaml_port = re.search(r"(?ms)^server:\s*(?:#.*)?\n(?:(?:[ \t]+.*)?\n)*?[ \t]+port:\s*([^#\r\n]+)", text)
        flat_context = re.search(r"(?m)^\s*server\.servlet\.context-path\s*=\s*([^#\r\n]+)", text)
        yaml_context = re.search(r"(?ms)^server:\s*\n(?:(?:[ \t]+.*)?\n)*?[ \t]+context-path:\s*([^#\r\n]+)", text)
        flat_swagger = re.search(r"(?m)^\s*springdoc\.swagger-ui\.path\s*=\s*([^#\r\n]+)", text)
        if flat_port or yaml_port: port = _resolved_value((flat_port or yaml_port).group(1), "8080")
        if flat_context or yaml_context: context_path = _resolved_value((flat_context or yaml_context).group(1), "")
        if flat_swagger: swagger_path = _resolved_value(flat_swagger.group(1), swagger_path)
    context_path = "/" + context_path.strip("/") if context_path.strip("/") else ""
    swagger_path = "/" + swagger_path.strip("/")
    base_url = f"http://127.0.0.1:{port}{context_path}"
    return {"detected": detected, "port": int(port) if port.isdigit() else port, "context_path": context_path,
            "base_url": base_url, "swagger_url": base_url + swagger_path,
            "openapi_url": base_url + "/v3/api-docs", "source": "configuração Spring Boot"}


