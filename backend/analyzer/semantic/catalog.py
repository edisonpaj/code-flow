from .endpoint_intent import INTENT_MAPPINGS
from .operation_classifier import OPERATION_MAPPINGS
from .responsibilities import ARCHITECTURAL_RESPONSIBILITIES
from .semantic_rules import OPERATION_FALLBACKS, RELATION_RULES, RETURN_RULES, SEMANTIC_RULES


def _rule_id(prefix: str, key: tuple) -> str:
    parts = [str(item).replace("_", "-") for item in key]
    return prefix + "-" + "-".join(parts)


def semantic_rules_catalog() -> list[dict]:
    result = []
    for key, template in SEMANTIC_RULES.items():
        source, target, intent, operation = key
        result.append({"id": _rule_id("SEM", key), "type": "EXACT", "source_role": source,
                       "target_role": target, "endpoint_intent": intent, "operation_kind": operation,
                       "template": template, "source_file": "backend/analyzer/semantic/semantic_rules.py"})
    for key, template in RELATION_RULES.items():
        source, target, operation = key
        result.append({"id": _rule_id("REL", key), "type": "RELATION", "source_role": source,
                       "target_role": target, "endpoint_intent": "*", "operation_kind": operation,
                       "template": template, "source_file": "backend/analyzer/semantic/semantic_rules.py"})
    for operation, template in OPERATION_FALLBACKS.items():
        result.append({"id": f"FALLBACK-{operation}", "type": "OPERATION", "source_role": "*",
                       "target_role": "*", "endpoint_intent": "*", "operation_kind": operation,
                       "template": template, "source_file": "backend/analyzer/semantic/semantic_rules.py"})
    return result


def return_rules_catalog() -> list[dict]:
    return [{"id": _rule_id("RETURN", key), "type": "RETURN", "source_role": key[0],
             "target_role": key[1], "operation_kind": key[2], "template": template,
             "source_file": "backend/analyzer/semantic/semantic_rules.py"}
            for key, template in RETURN_RULES.items()]


def responsibilities_catalog() -> list[dict]:
    return [{"role": role, **definition, "source_file": "backend/analyzer/semantic/responsibilities.py"}
            for role, definition in ARCHITECTURAL_RESPONSIBILITIES.items()]


def semantic_catalog() -> dict:
    rules = semantic_rules_catalog()
    return {"rules": rules, "return_rules": return_rules_catalog(),
            "responsibilities": responsibilities_catalog(), "intent_mappings": INTENT_MAPPINGS,
            "operation_mappings": OPERATION_MAPPINGS,
            "summary": {"exact_rules": sum(r["type"] == "EXACT" for r in rules),
                        "relation_rules": sum(r["type"] == "RELATION" for r in rules),
                        "fallback_rules": sum(r["type"] == "OPERATION" for r in rules),
                        "return_rules": len(RETURN_RULES)}}
