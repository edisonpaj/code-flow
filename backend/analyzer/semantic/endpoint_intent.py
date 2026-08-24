from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum


class EndpointIntent(str, Enum):
    LIST = "LIST"
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ACTION = "ACTION"
    UNKNOWN = "UNKNOWN"


INTENT_MAPPINGS = [
    {"http_method": "GET", "path_pattern": "coleção", "intent": "LIST", "evidence": "caminho sem variável"},
    {"http_method": "GET", "path_pattern": "/{id}", "intent": "READ", "evidence": "caminho com variável"},
    {"http_method": "POST", "path_pattern": "qualquer", "intent": "CREATE", "evidence": "método HTTP"},
    {"http_method": "PUT/PATCH", "path_pattern": "qualquer", "intent": "UPDATE", "evidence": "método HTTP"},
    {"http_method": "DELETE", "path_pattern": "qualquer", "intent": "DELETE", "evidence": "método HTTP"},
]


@dataclass
class EndpointContext:
    http_method: str
    path: str
    intent: str
    entity: str
    entity_plural: str
    entity_source: str
    controller: str
    operation: str
    http_status: int | None = None
    confidence: int = 0

    def to_dict(self): return asdict(self)


def detect_endpoint_intent(http_method: str, path: str) -> EndpointIntent:
    method = (http_method or "").upper()
    if method == "GET": return EndpointIntent.READ if "{" in path else EndpointIntent.LIST
    if method == "POST": return EndpointIntent.CREATE
    if method in {"PUT", "PATCH"}: return EndpointIntent.UPDATE
    if method == "DELETE": return EndpointIntent.DELETE
    return EndpointIntent.UNKNOWN


def _entity_from_path(path: str) -> tuple[str, str]:
    segments = [part for part in path.split("/") if part and not part.startswith("{") and not re.fullmatch(r"v\d+", part, re.I)]
    value = segments[-1] if segments else "recurso"
    irregular = {"clientes": "Cliente", "pedidos": "Pedido", "pessoas": "Pessoa", "itens": "Item"}
    singular = irregular.get(value.lower())
    if not singular:
        raw = value[:-1] if value.lower().endswith("s") else value
        singular = "".join(word.capitalize() for word in re.split(r"[-_]", raw)) or "Recurso"
    plural = value.replace("-", " ").replace("_", " ").lower()
    return singular, plural


def _confirmed_status(controller_source: str, method_line: int, method_body: str = "") -> int | None:
    lines = controller_source.splitlines()
    annotations = []
    cursor = method_line - 2
    while cursor >= 0:
        stripped = lines[cursor].strip()
        if not stripped:
            cursor -= 1; continue
        if stripped.startswith("@"):
            annotations.insert(0, stripped); cursor -= 1; continue
        break
    context = "\n".join(annotations) + "\n" + method_body
    if re.search(r"ResponseStatus\s*\(\s*(?:HttpStatus\.)?(?:NO_CONTENT|204)", context): return 204
    if re.search(r"ResponseStatus\s*\(\s*(?:HttpStatus\.)?(?:CREATED|201)", context): return 201
    if "ResponseEntity.noContent()" in context: return 204
    if "ResponseEntity.ok(" in context: return 200
    match = re.search(r"ResponseEntity\.status\s*\(\s*(\d{3})", context)
    return int(match.group(1)) if match else None


def build_endpoint_context(endpoint: dict, types: dict) -> EndpointContext:
    entity, plural = _entity_from_path(endpoint["path"])
    controller = types.get(endpoint["controller"])
    method = next((item for item in controller.methods if item.name == endpoint["method"] and item.line == endpoint["line"]), None) if controller else None
    status = _confirmed_status(controller.source, endpoint["line"], method.body if method else "") if controller else None
    return EndpointContext(endpoint["http_method"], endpoint["path"],
                           detect_endpoint_intent(endpoint["http_method"], endpoint["path"]).value,
                           entity, plural, "endpoint_path", endpoint["controller"], endpoint["method"], status, 90)
