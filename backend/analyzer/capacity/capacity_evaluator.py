from .config_scanner import scan
from .workload_calculator import workload, classify_headroom
from .score_calculator import score


def _metric(mid, title, status, value=None, detail="", evidence=None):
    return {"id": mid, "title": title, "status": status, "value": value, "detail": detail, "evidence": evidence or []}


def analyze_capacity(request):
    scanned = scan(request.project_path)
    cfg, ev = scanned["configuration"], scanned["evidence"]
    load = workload(request.target_tps, request.average_response_time_ms, cfg.get("replicas"), cfg.get("max_replicas"), request.headroom_percent)
    pressure = load["concurrency_per_pod"]
    metrics = []
    threads = cfg.get("tomcat_threads")
    thread_headroom = threads / pressure if threads and pressure else None
    metrics.append(_metric("threads", "Threads do servidor", classify_headroom(thread_headroom), threads, f"Headroom: {thread_headroom:.2f}x" if thread_headroom else "Configuração ou réplicas não encontradas", [ev["tomcat_threads"]] if "tomcat_threads" in ev else []))
    db_pool = cfg.get("hikari_pool")
    if not cfg["has_database"]: db_status = "NOT_APPLICABLE"
    elif db_pool is None or pressure is None: db_status = "UNKNOWN"
    elif db_pool >= pressure: db_status = "ADEQUATE"
    else: db_status = "POTENTIAL_BOTTLENECK"
    metrics.append(_metric("database_pool", "Pool de banco", db_status, db_pool, "Comparação conservadora; pool menor não prova insuficiência.", [ev["hikari_pool"]] if "hikari_pool" in ev else []))
    http_pool = cfg.get("http_pool")
    if not cfg["has_http_client"]: http_status = "NOT_APPLICABLE"
    else: http_status = classify_headroom(http_pool / pressure if http_pool and pressure else None)
    metrics.append(_metric("http_pool", "Pool HTTP", http_status, http_pool, "Pressão estimada com chamadas externas comprovadas.", [ev["http_pool"]] if "http_pool" in ev else []))
    replicas = cfg.get("replicas")
    metrics.append(_metric("pods", "Réplicas / Pods", "ADEQUATE" if replicas else "UNKNOWN", replicas, "Concorrência distribuída pelas réplicas declaradas.", [ev["replicas"]] if "replicas" in ev else []))
    hpa_status = "HEALTHY" if cfg["has_hpa"] and cfg.get("max_replicas") else ("ATTENTION" if cfg["has_manifests"] else "UNKNOWN")
    metrics.append(_metric("hpa", "Escalabilidade HPA", hpa_status, cfg.get("max_replicas"), "Capacidade máxima calculada apenas quando maxReplicas existe.", [ev[k] for k in ("min_replicas", "max_replicas") if k in ev]))
    resource_keys = ("cpu_request", "memory_request", "cpu_limit", "memory_limit")
    found_resources = sum(k in cfg for k in resource_keys)
    resource_status = "HEALTHY" if found_resources == 4 else ("ATTENTION" if found_resources else "UNKNOWN")
    metrics.append(_metric("resources", "CPU e memória", resource_status, {k: cfg.get(k) for k in resource_keys}, f"{found_resources}/4 configurações encontradas.", [ev[k] for k in resource_keys if k in ev]))
    timeout_status = "NOT_APPLICABLE" if not cfg["has_http_client"] else ("HEALTHY" if cfg.get("timeout_ms") else "ATTENTION")
    metrics.append(_metric("external_timeout", "Timeout externo", timeout_status, cfg.get("timeout_ms"), "Timeout explícito em integração externa.", [ev["timeout_ms"]] if "timeout_ms" in ev else []))
    blocking = cfg["blocking_calls"]
    metrics.append(_metric("blocking_calls", "Chamadas bloqueantes", "HEALTHY" if blocking == 0 else "ATTENTION", blocking, "Ocorrências estáticas comprovadas; não representa medição em runtime."))
    totals = score(metrics)
    severity = {"INSUFFICIENT": 0, "POTENTIAL_BOTTLENECK": 1, "ATTENTION": 2}
    bottlenecks = [m for m in metrics if m["status"] in severity]
    bottlenecks.sort(key=lambda m: severity[m["status"]])
    overall = "UNKNOWN" if totals["score"] is None or totals["confidence"] < 40 else ("HEALTHY" if totals["score"] >= 85 else "ADEQUATE" if totals["score"] >= 70 else "ATTENTION" if totals["score"] >= 50 else "INSUFFICIENT")
    detected = {key: cfg.get(key) for key in ("tomcat_threads", "hikari_pool", "cpu_request", "cpu_limit", "memory_request", "memory_limit", "min_replicas", "max_replicas")}
    diagnostics = [{"status": "ADEQUATE" if threads and threads >= load["estimated_concurrency"] else "ATTENTION" if threads else "NOT_DETECTED", "text": "Tomcat suporta a concorrência estimada" if threads and threads >= load["estimated_concurrency"] else "Tomcat threads abaixo da concorrência estimada" if threads else "Tomcat max threads não detectado"},
                   {"status": "ADEQUATE" if cfg["has_hpa"] else "NOT_DETECTED", "text": "HPA detectado" if cfg["has_hpa"] else "HPA não detectado"},
                   {"status": "NOT_DETERMINED", "text": "Capacidade por POD precisa de teste de carga ou observabilidade"}]
    for key, label in (("cpu_request", "CPU request"), ("cpu_limit", "CPU limit"), ("memory_request", "Memory request"), ("memory_limit", "Memory limit")):
        diagnostics.append({"status": "DETECTED" if cfg.get(key) else "NOT_DETECTED", "text": f"{label}: {cfg.get(key)}" if cfg.get(key) else f"{label} não detectado"})
    return {"independent_from_maturity": True, "input": request.model_dump(), "workload": load, "scan": scanned, "detected_configuration": detected,
            "capacity": {"real_tps_per_pod": None, "required_pods": None, "reason": "É necessário TPS/POD medido em teste de carga ou observabilidade para calcular réplicas com confiança."},
            "diagnostics": diagnostics, "recommendations": [item for item in scanned["configuration_files"] if item["status"] == "NOT_DETECTED"],
            "metrics": metrics, "score": totals["score"], "confidence": totals["confidence"], "status": overall, "bottlenecks": bottlenecks, "disclaimer": "Estimativa estática de capacidade. Não substitui testes de carga, APM ou métricas reais de produção."}
