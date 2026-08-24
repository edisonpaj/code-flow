from .models import JavaType


def implementation_index(types: dict[str, JavaType]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for item in types.values():
        for interface in item.interfaces:
            index.setdefault(interface, []).append(item.name)
    return index


def resolve(type_name: str, index: dict[str, list[str]], types: dict[str, JavaType]) -> str | None:
    candidates = index.get(type_name, [])
    if not candidates: return type_name if type_name in types else None
    preferred = sorted(candidates, key=lambda name: (types[name].layer not in {"Service", "Adapter OUT"}, name))
    return preferred[0]

