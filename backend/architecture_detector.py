from .models import JavaType


def detect_architecture(types: dict[str, JavaType]) -> dict:
    layers = {item.layer for item in types.values()}
    names = set(types)
    hexagonal, layered = [], []

    if "Port IN" in layers: hexagonal.append("diretório application/port/in")
    if "Port OUT" in layers: hexagonal.append("diretório application/port/out")
    if "Adapter IN" in layers: hexagonal.append("adaptador de entrada identificado")
    if "Adapter OUT" in layers: hexagonal.append("adaptador de saída identificado")
    use_cases = [interface for item in types.values() for interface in item.interfaces if interface.endswith("UseCase")]
    ports = [interface for item in types.values() for interface in item.interfaces if interface.endswith("Port")]
    if use_cases: hexagonal.append("serviços implementam Use Cases")
    if ports: hexagonal.append("adapters implementam Ports")

    if "Controller" in layers: layered.append("camada controller identificada")
    if "Service" in layers and "Port IN" not in layers: layered.append("camada service sem Port IN")
    if "Repository" in layers: layered.append("camada repository identificada")
    if any(name.endswith(("JpaRepository", "CrudRepository")) for name in names): layered.append("Spring Data Repository identificado")
    if "Entity" in layers: layered.append("camada entity identificada")

    hex_score = min(100, len(hexagonal) * 18)
    layered_score = min(100, len(layered) * 25)
    if hex_score >= 54 and layered_score >= 50:
        kind, label = "HYBRID", "Híbrida (Hexagonal + Layered)"
    elif hex_score >= 54:
        kind, label = "HEXAGONAL", "Hexagonal"
    elif layered_score >= 50:
        kind, label = "LAYERED", "Layered"
    else:
        kind, label = "UNKNOWN", "Não determinada"
    confidence = max(hex_score, layered_score)
    expected = (["Adapter IN", "Port IN", "Use Case/Service", "Port OUT", "Adapter OUT", "Repository", "Database"]
                if kind in {"HEXAGONAL", "HYBRID"} else
                ["Controller", "Service", "Repository", "Database"] if kind == "LAYERED" else [])
    return {"type": kind, "label": label, "confidence": confidence,
            "evidence": hexagonal + layered, "scores": {"hexagonal": hex_score, "layered": layered_score},
            "expected_flow": expected}
