from __future__ import annotations

from dataclasses import asdict, dataclass

from ..models import JavaType


ROLES = {
    "HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "USE_CASE_PORT", "PERSISTENCE_PORT",
    "PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "HTTP_CLIENT", "MESSAGE_PRODUCER",
    "MESSAGE_CONSUMER", "DOMAIN_OBJECT", "MAPPER", "UNKNOWN",
}


@dataclass
class Classification:
    role: str
    confidence: int
    reasons: list[str]


def _used_by(item: JavaType, types: dict[str, JavaType]) -> list[JavaType]:
    return [owner for owner in types.values() if item.name in owner.fields.values()]


def classify_type(item: JavaType, types: dict[str, JavaType]) -> dict:
    annotations = set(item.annotations)
    source = item.source
    reasons: list[str] = []
    role = "UNKNOWN"
    score = 0

    if annotations & {"RestController", "Controller"} or any(a.endswith("Mapping") for a in annotations):
        role, score = "HTTP_ENTRYPOINT", 100
        reasons.append("expõe endpoint HTTP por anotação Spring MVC")
    elif "FeignClient" in annotations or any(token in source for token in ("WebClient", "RestClient", "RestTemplate")):
        role, score = "HTTP_CLIENT", 95
        reasons.append("integração HTTP Spring identificada")
    elif "KafkaListener" in annotations:
        role, score = "MESSAGE_CONSUMER", 100
        reasons.append("consumidor declarado com @KafkaListener")
    elif "KafkaTemplate" in source:
        role, score = "MESSAGE_PRODUCER", 95
        reasons.append("dependência de KafkaTemplate identificada")
    elif item.kind == "interface" and any(base in {"JpaRepository", "CrudRepository", "PagingAndSortingRepository"} for base in item.extends):
        role, score = "DATABASE_REPOSITORY", 100
        reasons.append("estende repositório Spring Data")
    elif "Service" in annotations:
        role, score = "APPLICATION_SERVICE", 100
        reasons.append("classe anotada com @Service")
    elif item.kind == "interface":
        consumers = _used_by(item, types)
        implementations = [owner for owner in types.values() if item.name in owner.interfaces]
        if consumers and implementations:
            if any(classify_type(owner, types)["role"] == "HTTP_ENTRYPOINT" for owner in consumers):
                role, score = "USE_CASE_PORT", 90
                reasons.append("interface usada por entrada HTTP e implementada pela aplicação")
            elif any(("Service" in owner.annotations or owner.layer == "Service") for owner in consumers):
                role, score = "PERSISTENCE_PORT", 90
                reasons.append("interface usada pelo serviço e implementada por adaptador")
    elif any(types.get(contract) and classify_type(types[contract], types)["role"] == "PERSISTENCE_PORT" for contract in item.interfaces):
        if any(types.get(dependency) and classify_type(types[dependency], types)["role"] == "DATABASE_REPOSITORY" for dependency in item.fields.values()):
            role, score = "PERSISTENCE_ADAPTER", 100
            reasons.append("implementa porta de persistência e depende de Spring Data")
    if role == "UNKNOWN" and (item.layer == "Domain" or "Entity" in annotations):
        role, score = "DOMAIN_OBJECT", 75
        reasons.append("tipo de domínio identificado por evidência estrutural")
    if role == "UNKNOWN" and ("Mapper" in annotations or item.name.endswith("Mapper")):
        role, score = "MAPPER", 70
        reasons.append("mapper identificado por anotação ou convenção auxiliar")
    if role == "UNKNOWN" and item.layer == "Service":
        role, score = "APPLICATION_SERVICE", 65
        reasons.append("pacote de serviço usado como evidência auxiliar")
    if role == "UNKNOWN":
        reasons.append("evidência Spring/Java insuficiente")
    return asdict(Classification(role, score, reasons))


def classify_project(types: dict[str, JavaType]) -> dict[str, dict]:
    return {name: classify_type(item, types) for name, item in types.items()}
