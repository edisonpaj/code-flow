def workload(target_tps: float, response_ms: float, replicas: int | None = None, max_replicas: int | None = None, headroom_percent: float = 0):
    concurrency = target_tps * (response_ms / 1000.0)
    design_tps = target_tps * (1 + headroom_percent / 100.0)
    return {
        "target_tps": target_tps,
        "average_response_time_ms": response_ms,
        "estimated_concurrency": round(concurrency, 2),
        "headroom_percent": headroom_percent,
        "design_tps": round(design_tps, 2),
        "current_replicas": replicas,
        "concurrency_per_pod": round(concurrency / replicas, 2) if replicas else None,
        "max_replicas": max_replicas,
        "concurrency_per_pod_at_max_scale": round(concurrency / max_replicas, 2) if max_replicas else None,
    }


def classify_headroom(headroom: float | None) -> str:
    if headroom is None: return "UNKNOWN"
    if headroom >= 2: return "HEALTHY"
    if headroom >= 1.5: return "ADEQUATE"
    if headroom >= 1: return "ATTENTION"
    return "INSUFFICIENT"
