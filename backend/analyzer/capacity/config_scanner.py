import re
from pathlib import Path

TEXT_EXTENSIONS = {".java", ".xml", ".yml", ".yaml", ".properties", ".gradle"}
SKIP = {"target", "build", ".git", ".idea", "node_modules"}

PATTERNS = {
    "replicas": [r"(?mi)^\s*(?:replicaCount|replicas)\s*:\s*(\d+)"],
    "max_replicas": [r"(?mi)^\s*maxReplicas\s*:\s*(\d+)"],
    "min_replicas": [r"(?mi)^\s*minReplicas\s*:\s*(\d+)"],
    "tomcat_threads": [r"(?mi)^\s*server\.tomcat\.threads\.max\s*[=:]\s*(\d+)", r"(?mi)^\s*max-threads\s*:\s*(\d+)"],
    "hikari_pool": [r"(?mi)^\s*(?:spring\.datasource\.hikari\.)?maximum-pool-size\s*[=:]\s*(\d+)"],
    "http_pool": [r"(?i)(?:maxConnections|max-connections)\s*(?:\(|[=:])\s*(\d+)"],
    "timeout_ms": [r"(?mi)^\s*[^#\n]*(?:connect|read|response)[-.]?timeout[^:=\n]*[=:]\s*([0-9]+(?:ms|s)?)"],
    "cpu_request": [r"(?is)requests\s*:\s*.{0,180}?cpu\s*:\s*[\"']?([^\s\"']+)"],
    "memory_request": [r"(?is)requests\s*:\s*.{0,220}?memory\s*:\s*[\"']?([^\s\"']+)"],
    "cpu_limit": [r"(?is)limits\s*:\s*.{0,180}?cpu\s*:\s*[\"']?([^\s\"']+)"],
    "memory_limit": [r"(?is)limits\s*:\s*.{0,220}?memory\s*:\s*[\"']?([^\s\"']+)"],
}


def scan(project_path: str):
    root = Path(project_path).resolve()
    if not root.is_dir(): raise ValueError("Diretório do microsserviço não encontrado")
    files = [p for p in root.rglob("*") if p.is_file() and not SKIP.intersection(p.parts) and (p.suffix.lower() in TEXT_EXTENSIONS or p.name == "Dockerfile")]
    corpus = []
    for path in files:
        try: corpus.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError: pass
    values, evidence = {}, {}
    for key, patterns in PATTERNS.items():
        for path, text in corpus:
            match = next((m for pattern in patterns if (m := re.search(pattern, text))), None)
            if match:
                raw = match.group(1).rstrip(",}")
                values[key] = int(raw) if raw.isdigit() else raw
                evidence[key] = {"file": str(path.relative_to(root)), "line": text.count("\n", 0, match.start()) + 1, "snippet": match.group(0).strip()[:180]}
                break
    all_text = "\n".join(text for _, text in corpus)
    java_text = "\n".join(text for path, text in corpus if path.suffix.lower() == ".java")
    values.update({
        "has_database": bool(re.search(r"(?i)JpaRepository|CrudRepository|spring-data-jpa|datasource", all_text)),
        "has_http_client": bool(re.search(r"(?i)WebClient|RestClient|RestTemplate|FeignClient", all_text)),
        "has_hpa": bool(re.search(r"(?i)kind\s*:\s*HorizontalPodAutoscaler|autoscaling\s*:\s*\n?.*enabled\s*:\s*true", all_text)),
        "has_manifests": bool(re.search(r"(?i)kind\s*:\s*(Deployment|DeploymentConfig|StatefulSet)", all_text)),
        "blocking_calls": len(re.findall(r"\.block\s*\(|Thread\.sleep\s*\(|\bsynchronized\b", java_text)),
    })
    def located(label, predicate, found_values, recommendation, example):
        matched = [str(path.relative_to(root)) for path, _ in corpus if predicate(path)]
        return {"name": label, "status": "DETECTED" if matched else "NOT_DETECTED", "files": matched,
                "values": {key: values.get(key) for key in found_values if values.get(key) is not None},
                "recommendation": None if matched else recommendation, "example": None if matched else example}
    file_inventory = [
        located("application.yml", lambda p: p.name in {"application.yml", "application.yaml", "application.properties"}, ("tomcat_threads", "hikari_pool", "timeout_ms"), "Considere explicitar parâmetros de runtime, Tomcat e pool de conexões.", "server:\n  tomcat:\n    threads:\n      max: 200\nspring:\n  datasource:\n    hikari:\n      maximum-pool-size: 20"),
        located("values.yaml", lambda p: p.name in {"values.yml", "values.yaml"}, ("cpu_request", "cpu_limit", "memory_request", "memory_limit", "min_replicas", "max_replicas"), "Considere adicionar Helm com requests/limits e autoscaling.", "resources:\n  requests: { cpu: 250m, memory: 512Mi }\n  limits: { cpu: 1, memory: 1Gi }\nautoscaling:\n  minReplicas: 2\n  maxReplicas: 6"),
        located("Dockerfile", lambda p: p.name == "Dockerfile", (), "Considere adicionar Dockerfile para padronizar imagem e parâmetros da JVM.", "FROM eclipse-temurin:21-jre\nENV JAVA_TOOL_OPTIONS=\"-XX:MaxRAMPercentage=75\"\nCOPY app.jar /app.jar\nENTRYPOINT [\"java\",\"-jar\",\"/app.jar\"]"),
        located("Deployment", lambda p: p.suffix.lower() in {".yml", ".yaml"} and re.search(r"(?i)kind\s*:\s*(Deployment|DeploymentConfig|StatefulSet)", dict(corpus).get(p, "")), ("replicas", "cpu_request", "cpu_limit", "memory_request", "memory_limit"), "Considere declarar Deployment, resources e probes no template Kubernetes/OpenShift.", "kind: Deployment\nspec:\n  replicas: 2\n  template:\n    spec:\n      containers:\n      - resources: { requests: { cpu: 250m, memory: 512Mi } }"),
        located("HPA", lambda p: p.suffix.lower() in {".yml", ".yaml"} and re.search(r"(?i)kind\s*:\s*HorizontalPodAutoscaler", dict(corpus).get(p, "")), ("min_replicas", "max_replicas"), "Considere habilitar HPA quando houver carga variável e métricas disponíveis.", "kind: HorizontalPodAutoscaler\nspec:\n  minReplicas: 2\n  maxReplicas: 6\n  metrics:\n  - resource:\n      name: cpu\n      target: { averageUtilization: 70 }"),
    ]
    return {"project": str(root), "configuration": values, "evidence": evidence, "files_inspected": len(corpus), "configuration_files": file_inventory}
