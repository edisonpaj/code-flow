import re
from pathlib import Path

from .java_parser import endpoints, parse_project

IGNORED_PARTS = {"target", "build", ".git", ".gradle", ".idea"}

def _java_files(project: Path) -> list[Path]:
    return [path for path in project.rglob("*.java") if not any(part in IGNORED_PARTS for part in path.parts)]

def _build_catalog(project: Path) -> tuple[list[dict], dict]:
    dependencies: dict[str, dict] = {}
    versions: dict[str, str] = {}
    for pom in project.rglob("pom.xml"):
        if any(part in IGNORED_PARTS for part in pom.parts): continue
        text = pom.read_text(encoding="utf-8", errors="ignore")
        properties_block = re.search(r"<properties>(.*?)</properties>", text, re.S)
        properties = dict(re.findall(r"<([\w.-]+)>([^<]+)</\1>", properties_block.group(1) if properties_block else ""))
        def resolve(value: str) -> str:
            match = re.fullmatch(r"\$\{([^}]+)}", value.strip())
            return properties.get(match.group(1), value).strip() if match else value.strip()
        java = next((properties[key] for key in ("java.version", "maven.compiler.release", "maven.compiler.source") if key in properties), None)
        if java: versions["Java"] = resolve(java)
        parent = re.search(r"<parent>(.*?)</parent>", text, re.S)
        if parent and "spring-boot" in parent.group(1):
            parent_version = re.search(r"<version>(.*?)</version>", parent.group(1), re.S)
            if parent_version: versions["Spring Boot"] = resolve(parent_version.group(1))
        for block in re.findall(r"<dependency>(.*?)</dependency>", text, re.S):
            group = re.search(r"<groupId>(.*?)</groupId>", block, re.S)
            artifact = re.search(r"<artifactId>(.*?)</artifactId>", block, re.S)
            version = re.search(r"<version>(.*?)</version>", block, re.S)
            scope = re.search(r"<scope>(.*?)</scope>", block, re.S)
            if artifact:
                artifact_id, group_id = artifact.group(1).strip(), group.group(1).strip() if group else ""
                scope_value = scope.group(1).strip() if scope else "compile"
                item = {"name": artifact_id, "group": group_id, "version": resolve(version.group(1)) if version else "Gerenciada pelo Spring Boot", "scope": scope_value}
                dependencies[f"{group_id}:{artifact_id}"] = item
                if version and scope_value != "test" and not artifact_id.startswith("spring-boot-starter"):
                    versions.setdefault(artifact_id, item["version"])
    for name in ("build.gradle", "build.gradle.kts"):
        for build in project.rglob(name):
            if any(part in IGNORED_PARTS for part in build.parts): continue
            text = build.read_text(encoding="utf-8", errors="ignore")
            java = re.search(r"(?:sourceCompatibility\s*=|JavaLanguageVersion\.of\s*\()\s*[\"']?(\d+)", text)
            spring = re.search(r"id\s*\(?[\"']org\.springframework\.boot[\"']\)?\s*version\s*[\"']([^\"']+)", text)
            if java: versions["Java"] = java.group(1)
            if spring: versions["Spring Boot"] = spring.group(1)
            for scope, coordinate in re.findall(r"(?m)^\s*(implementation|api|compileOnly|runtimeOnly|testImplementation)\s*\(?[\"']([^\"']+)", text):
                parts = coordinate.split(":")
                group, artifact = (parts[0], parts[1]) if len(parts) > 1 else ("", parts[0])
                version = parts[2] if len(parts) > 2 else "Gerenciada pelo framework"
                dependencies[f"{group}:{artifact}"] = {"name": artifact, "group": group, "version": version, "scope": scope}
                if scope != "testImplementation" and version != "Gerenciada pelo framework": versions.setdefault(artifact, version)
    return sorted(dependencies.values(), key=lambda item: (item["scope"], item["name"])), versions

def analyze_microservice(project_path: str) -> dict:
    project = Path(project_path).resolve()
    if not project.is_dir(): raise ValueError("Diretório do microsserviço não encontrado")
    files = _java_files(project)
    sources = {path: path.read_text(encoding="utf-8", errors="ignore") for path in files}
    all_java = "\n".join(sources.values())
    all_types = parse_project(project)
    types = {name: item for name, item in all_types.items() if "test" not in {part.lower() for part in item.path.parts}}
    items = list(types.values())
    rest_controllers = [x for x in items if x.kind == "class" and "RestController" in x.annotations and "RestControllerAdvice" not in x.annotations]
    mvc_controllers = [x for x in items if x.kind == "class" and "Controller" in x.annotations and not any(a in x.annotations for a in ("ControllerAdvice", "RestControllerAdvice", "RestController"))]
    exception_handlers = [x for x in items if any(a in x.annotations for a in ("ControllerAdvice", "RestControllerAdvice"))]
    technical_controllers = [x for x in items if any(a in x.annotations for a in ("Endpoint", "RestControllerEndpoint", "ControllerEndpoint"))]
    services = [x for x in items if x.kind == "class" and ("Service" in x.annotations or x.layer == "Service")]
    port_out_names = {x.name for x in items if x.layer == "Port OUT"}
    adapters_out = [x for x in items if x.kind == "class" and any(interface in port_out_names or interface.endswith(("Port", "PortOut")) for interface in x.interfaces)]
    repositories = [x for x in items if x.kind == "interface" and ("Repository" in x.annotations or any(base.endswith(("JpaRepository", "CrudRepository", "PagingAndSortingRepository")) for base in x.extends))]
    jpa_entities = [x for x in items if x.kind in {"class", "record"} and "Entity" in x.annotations]
    rest_endpoints = sum(bool(method.http_method) for controller in rest_controllers for method in controller.methods)
    endpoint_details = [{"name": f"{method.http_method} {('/' + '/'.join(part.strip('/') for part in (controller.base_mapping, method.mapping or '') if part.strip('/'))) or '/'}", "owner": controller.name}
                        for controller in rest_controllers for method in controller.methods if method.http_method]
    configs = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for pattern in ("*.yml", "*.yaml", "*.properties") for path in project.rglob(pattern) if not any(part in IGNORED_PARTS for part in path.parts))
    configured_databases = set(re.findall(r"(?im)^\s*(?:spring\.)?datasource(?:s)?(?:\.([\w-]+)|\[([^]]+)\])", configs))
    has_database = bool(re.search(r"JpaRepository|CrudRepository|jdbc:|datasource", all_java + configs, re.I))
    producer_pattern = re.compile(r"\b(?:KafkaTemplate|RabbitTemplate|JmsTemplate|StreamBridge)\b|\.send\s*\(", re.I)
    consumer_pattern = re.compile(r"@(?:KafkaListener|RabbitListener|JmsListener)\b|\bConsumer\s*<", re.I)
    producers = sum(bool(producer_pattern.search(text)) for text in sources.values())
    consumers = sum(bool(consumer_pattern.search(text)) for text in sources.values())
    external_patterns = (r"@FeignClient\b", r"\bRestTemplate\b", r"\bWebClient\b", r"\bHttpClient\b", r"\bRestClient\b", r"@HttpExchange\b")
    dependency_catalog, versions = _build_catalog(project)
    return {"microservice": project.name,
        "code": {"java_files": len(files), "classes": sum(x.kind in {"class", "record"} for x in items), "interfaces": sum(x.kind == "interface" for x in items), "methods": sum(len(x.methods) for x in items), "lines_of_code": sum(len(text.splitlines()) for text in sources.values()), "dependencies": len(dependency_catalog)},
        "dependencies": dependency_catalog, "versions": versions,
        "architecture": {"rest_controllers": len(rest_controllers), "rest_endpoints": rest_endpoints, "exception_handlers": len(exception_handlers), "technical_controllers": len(technical_controllers), "services": len(services), "ports_in": sum(x.layer == "Port IN" and x.kind == "interface" for x in items), "ports_out": len(port_out_names), "adapters_out": len(adapters_out), "repositories": len(repositories), "jpa_entities": len(jpa_entities),
            "details": {"controllers": [{"name": x.name, "endpoints": sum(bool(m.http_method) for m in x.methods)} for x in rest_controllers], "endpoints": endpoint_details, "services": [x.name for x in services], "ports_in": [x.name for x in items if x.layer == "Port IN" and x.kind == "interface"], "ports_out": sorted(port_out_names), "adapters_out": [x.name for x in adapters_out], "repositories": [x.name for x in repositories], "jpa_entities": [x.name for x in jpa_entities], "excluded_from_controllers": [x.name for x in exception_handlers + technical_controllers]}},
        "integrations": {"external_calls": sum(len(re.findall(p, all_java)) for p in external_patterns), "databases": len(configured_databases) or (1 if has_database else 0), "event_producers": producers, "event_consumers": consumers}}
