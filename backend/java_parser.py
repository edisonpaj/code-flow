import re
import os
from pathlib import Path
from .models import JavaType, MethodInfo


TYPE_RE = re.compile(r"\b(public\s+)?(class|interface|record)\s+(\w+)(?:\s*\([^{}]*\))?(?:\s+extends\s+([^\{]+?))?(?:\s+implements\s+([^\{]+))?\s*\{")
METHOD_RE = re.compile(r"(?m)^\s*(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?P<return>[\w<>?,.\[\]]+)\s+(?P<name>\w+)\s*\((?P<params>[^;{}]*)\)\s*(?:throws\s+(?P<throws>[^\{]+))?\{")
FIELD_RE = re.compile(r"(?m)^\s*private\s+(?:final\s+)?([\w<>?,.]+)\s+(\w+)\s*;")
MAPPING_RE = re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping(?:\(([^)]*)\))?")
IGNORED_DIRS = {".git", ".gradle", ".idea", ".mvn", ".settings", ".vscode", "build", "dist", "node_modules", "out", "target"}


def _brace_end(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if char == '"' and not escaped:
            in_string = not in_string
        escaped = char == "\\" and not escaped
        if in_string:
            continue
        if char == "{": depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0: return i
    return len(text) - 1


def _mapping(annotation: str) -> tuple[str | None, str | None]:
    matches = list(MAPPING_RE.finditer(annotation))
    match = matches[-1] if matches else None
    if not match: return None, None
    kind, args = match.groups()
    method = kind.upper() if kind != "Request" else None
    if kind == "Request" and args:
        found = re.search(r"RequestMethod\.(GET|POST|PUT|DELETE|PATCH)", args)
        method = found.group(1) if found else None
    path = ""
    if args:
        found = re.search(r'(?:value\s*=|path\s*=)?\s*"([^"]*)"', args)
        path = found.group(1) if found else ""
    return method, path


def classify(path: Path) -> str:
    value = str(path).replace("\\", "/").lower()
    for marker, layer in (("application/port/in", "Port IN"), ("application/port/out", "Port OUT"),
                          ("application/service", "Service"), ("adapter/in", "Adapter IN"),
                          ("adapter/out", "Adapter OUT"), ("domain", "Domain"),
                          ("infrastructure", "Infrastructure")):
        if marker in value: return layer
    for marker, layer in (("/controller/", "Controller"), ("/controllers/", "Controller"),
                          ("/repository/", "Repository"), ("/repositories/", "Repository"),
                          ("/entity/", "Entity"), ("/entities/", "Entity"),
                          ("/service/", "Service"), ("/services/", "Service")):
        if marker in value: return layer
    return "Java"


def parse_project(project: Path) -> dict[str, JavaType]:
    types = {}
    for path in project.rglob("*.java"):
        if any(part in {"target", "build", ".git"} for part in path.parts): continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        type_match = TYPE_RE.search(text)
        if not type_match: continue
        _, kind, name, extended, implemented = type_match.groups()
        interfaces = re.findall(r"\b\w+\b", implemented or "")
        extended_types = re.findall(r"\b\w+\b", extended or "")
        package_match = re.search(r"package\s+([\w.]+)\s*;", text)
        header = text[:type_match.start()]
        _, base = _mapping(header)
        fields = {variable: declared_type for declared_type, variable in FIELD_RE.findall(text)}
        annotations = re.findall(r"@(\w+)", header)
        item = JavaType(name, kind, path, package_match.group(1) if package_match else "", classify(path), interfaces, fields)
        item.base_mapping = base or ""
        item.annotations = annotations
        item.extends = extended_types
        item.source = text
        scan_boundary = type_match.end()
        for match in METHOD_RE.finditer(text, type_match.end()):
            brace = text.find("{", match.start())
            end = _brace_end(text, brace)
            before = text[scan_boundary:match.start()]
            http, mapping = _mapping(before)
            declared_throws = re.findall(r"\b\w+(?:Exception|Error)\b", match.group("throws") or "")
            body = text[brace + 1:end]
            declared_throws.extend(x for x in re.findall(r"throw\s+new\s+(\w+)", body) if x not in declared_throws)
            item.methods.append(MethodInfo(match.group("name"), text.count("\n", 0, match.start()) + 1,
                                           text.count("\n", 0, end) + 1, body, mapping, http,
                                           match.group("return"), " ".join(match.group("params").split()), declared_throws))
            scan_boundary = end + 1
        types[name] = item
    return types


def endpoints(types: dict[str, JavaType]) -> list[dict]:
    result = []
    for owner in types.values():
        for method in owner.methods:
            if method.http_method:
                path = "/" + "/".join(x.strip("/") for x in (owner.base_mapping, method.mapping or "") if x.strip("/"))
                result.append({"id": f"{owner.name}:{method.name}:{method.line}", "http_method": method.http_method,
                               "path": path or "/", "controller": owner.name, "method": method.name, "line": method.line})
    return sorted(result, key=lambda x: (x["path"], x["http_method"]))


