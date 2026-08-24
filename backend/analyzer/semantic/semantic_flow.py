from __future__ import annotations

import re

from .endpoint_intent import EndpointContext
from .operation_classifier import OperationKind, classify_operation
from .responsibilities import ARCHITECTURAL_RESPONSIBILITIES
from .semantic_rules import OPERATION_FALLBACKS, RELATION_RULES, RETURN_RULES, SEMANTIC_RULES

VISIBLE_ROLES = {"HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "DOMAIN_OBJECT", "PERSISTENCE_ADAPTER",
                 "DATABASE_REPOSITORY", "HTTP_CLIENT", "MESSAGE_PRODUCER", "MESSAGE_CONSUMER"}
ROLE_LABELS = {"HTTP_ENTRYPOINT": "API", "APPLICATION_SERVICE": "Serviço", "DOMAIN_OBJECT": "Domínio",
               "PERSISTENCE_ADAPTER": "Persistência", "DATABASE_REPOSITORY": "Banco de Dados",
               "HTTP_CLIENT": "Serviço Externo", "MESSAGE_PRODUCER": "Publicador de Eventos",
               "MESSAGE_CONSUMER": "Consumidor de Eventos"}


def _subject(name: str, context: EndpointContext) -> str:
    clean = re.sub(r"(Controller|Service|PersistenceAdapter|RepositoryAdapter|JpaRepository|Repository|Adapter)$", "", name)
    subject = re.sub(r"(?<!^)(?=[A-Z])", " ", clean).strip()
    return context.entity_plural.title() if subject.lower() == context.entity.lower() else (subject or name)


def _format(template: str, context: EndpointContext, operation: str) -> str:
    return template.format(entity=context.entity.lower(), entities=context.entity_plural.lower(),
                           entity_title=context.entity, operation=operation)


def _client_message(context: EndpointContext) -> str:
    messages = {"LIST": "Solicita lista de {entities}", "READ": "Solicita consulta do {entity}",
                "CREATE": "Solicita criação do {entity}", "UPDATE": "Solicita atualização do {entity}",
                "DELETE": "Solicita exclusão do {entity}"}
    return _format(messages.get(context.intent, "Solicita operação sobre {entity}"), context, context.operation)


def resolve_message(source_role: str, target_role: str, context: EndpointContext,
                    operation_kind: str, technical_method: str) -> tuple[str, str]:
    if source_role == "ACTOR" and target_role == "HTTP_ENTRYPOINT": return _client_message(context), "CLIENT_INTENT"
    effective_kind = "CALL" if source_role == "HTTP_ENTRYPOINT" and target_role == "APPLICATION_SERVICE" else operation_kind
    exact = SEMANTIC_RULES.get((source_role, target_role, context.intent, effective_kind))
    if exact: return _format(exact, context, technical_method), "EXACT"
    relation = RELATION_RULES.get((source_role, target_role, effective_kind))
    if relation: return _format(relation, context, technical_method), "RELATION"
    fallback = OPERATION_FALLBACKS.get(effective_kind)
    if fallback: return _format(fallback, context, technical_method), "OPERATION"
    humanized = re.sub(r"(?<!^)(?=[A-Z])", " ", technical_method).lower()
    return humanized or technical_method, "TECHNICAL_FALLBACK"


def resolve_return(source_role: str, target_role: str, context: EndpointContext,
                   operation_kind: str) -> tuple[str, str]:
    if target_role == "ACTOR":
        return (f"HTTP {context.http_status}" if context.http_status else "Resposta HTTP"), ("CODE_EVIDENCE" if context.http_status else "SAFE_FALLBACK")
    template = RETURN_RULES.get((source_role, target_role, operation_kind))
    if template: return _format(template, context, ""), "EXACT_RETURN"
    if operation_kind == "FIND": return context.entity, "OPERATION_RETURN"
    return "Operação concluída", "SAFE_FALLBACK"


def build_semantic_flow(raw_model: dict, classifications: dict[str, dict], context: EndpointContext) -> dict:
    raw_participants = {p["id"]: p for p in raw_model["participants"]}
    participants = [{"id": "client", "display_name": "Cliente/API Client", "technical_name": "Cliente/API Client",
                     "role": "ACTOR", "responsibility": "Iniciar a interação com a API.", "file": "", "line": 0, "type": "actor"}]
    raw_to_semantic = {"client": "client"}
    role_by_semantic = {"client": "ACTOR"}
    for raw in raw_model["participants"]:
        if raw["id"] == "client": continue
        role = classifications.get(raw["classifier"], {"role": "UNKNOWN"})["role"]
        if role not in VISIBLE_ROLES: continue
        semantic_id = f"semantic_{len(participants)}"
        raw_to_semantic[raw["id"]] = semantic_id; role_by_semantic[semantic_id] = role
        subject = _subject(raw["classifier"], context)
        display = "Banco de Dados" if role == "DATABASE_REPOSITORY" else f"{ROLE_LABELS[role]} de {subject}"
        responsibility = ARCHITECTURAL_RESPONSIBILITIES.get(role, ARCHITECTURAL_RESPONSIBILITIES["UNKNOWN"])["responsibility"]
        participants.append({"id": semantic_id, "display_name": display, "technical_name": raw["classifier"],
                             "role": role, "responsibility": responsibility, "file": raw.get("file", ""),
                             "line": raw.get("line", 0), "type": "participant"})

    call_meta: dict[str, dict] = {}
    interactions, semantic_events = [], []
    for event in raw_model["events"]:
        if event["type"] == "call":
            source = raw_to_semantic.get(event.get("semantic_caller", event["caller"]))
            target = raw_to_semantic.get(event["callee"])
            operation = classify_operation(event["method"]).value
            call_meta[event["id"]] = {"source": source, "target": target, "operation_kind": operation}
            if not source or not target or source == target: continue
            source_role, target_role = role_by_semantic[source], role_by_semantic[target]
            description, rule_level = resolve_message(source_role, target_role, context, operation, event["method"])
            item = {"type": "call", "id": event["id"], "parent_call_id": event.get("parent_call_id"),
                    "source": source, "target": target, "source_role": source_role, "target_role": target_role,
                    "technical_operation": event["signature"], "operation_kind": operation,
                    "functional_description": description, "rule_level": rule_level,
                    "protocol": "HTTP" if source == "client" else "Java", "synchronous": True,
                    "file": event.get("file", ""), "line": event.get("line", 0),
                    "return_type": event.get("return_type", "resultado")}
            interactions.append(item); semantic_events.append(item)
        elif event["type"] == "return":
            meta = call_meta.get(event["call_id"])
            if not meta or not meta["source"] or not meta["target"] or meta["source"] == meta["target"]: continue
            source, target = meta["target"], meta["source"]
            source_role, target_role = role_by_semantic[source], role_by_semantic[target]
            description, rule_level = resolve_return(source_role, target_role, context, meta["operation_kind"])
            semantic_events.append({"type": "return", "call_id": event["call_id"], "source": source, "target": target,
                                    "source_role": source_role, "target_role": target_role,
                                    "operation_kind": meta["operation_kind"], "functional_description": description,
                                    "rule_level": rule_level})
        elif event["type"] == "exception":
            source, target = raw_to_semantic.get(event["from"]), raw_to_semantic.get(event["to"])
            if source and target and source != target:
                semantic_events.append({"type": "exception", "call_id": event["call_id"], "source": source, "target": target,
                                        "functional_description": event["exception"], "rule_level": "CODE_EVIDENCE"})
    return {"interaction": raw_model["interaction"], "endpoint_context": context.to_dict(),
            "participants": participants, "interactions": interactions, "events": semantic_events,
            "diagram_type": "INTERNAL", "detail_level": "ARCHITECTURAL"}


def semantic_mermaid(flow: dict) -> str:
    lines = ["sequenceDiagram", "    autonumber"]
    for participant in flow["participants"]:
        keyword = "actor" if participant["type"] == "actor" else "participant"
        lines.append(f"    {keyword} {participant['id']} as {participant['display_name']}")
    first, last = flow["participants"][0]["id"], flow["participants"][-1]["id"]
    lines.append(f"    Note over {first},{last}: sd {flow['interaction']}")
    for event in flow["events"]:
        if event["type"] == "call": lines.append(f"    {event['source']}->>+{event['target']}: {event['functional_description']}")
        elif event["type"] == "return": lines.append(f"    {event['source']}-->>-{event['target']}: {event['functional_description']}")
        else: lines.append(f"    {event['source']}--x{event['target']}: {event['functional_description']}")
    return "\n".join(lines)
