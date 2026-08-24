from __future__ import annotations

import re
from pathlib import Path

IGNORED = {"target", "build", ".git", ".idea", ".venv", "node_modules"}
TEXT_SUFFIXES = {".java", ".xml", ".gradle", ".yml", ".yaml", ".properties", ".conf"}


class ScanContext:
    def __init__(self, project_path: str):
        self.root = Path(project_path).resolve()
        if not self.root.exists(): raise ValueError("Projeto não encontrado")
        self.files = []
        for path in self.root.rglob("*"):
            if not path.is_file() or any(part.lower() in IGNORED for part in path.parts): continue
            if path.suffix.lower() in TEXT_SUFFIXES or path.name.lower() in {"dockerfile", "jenkinsfile", "mvnw", "mvnw.cmd"}:
                self.files.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        self.test_java = [(p, t) for p, t in self.files if p.suffix.lower() == ".java" and
                          any(part.lower() in {"test", "tests"} for part in p.parts)]
        self.java = [(p, t) for p, t in self.files if p.suffix.lower() == ".java" and
                     not any(part.lower() in {"test", "tests"} for part in p.parts)]
        self.build = [(p, t) for p, t in self.files if p.name in {"pom.xml", "build.gradle", "build.gradle.kts"}]
        self.config = [(p, t) for p, t in self.files if p.name.startswith("application.")]
        self.docker = [(p, t) for p, t in self.files if p.name.lower() == "dockerfile"]
        self.manifests = [(p, t) for p, t in self.files if p.suffix.lower() in {".yml", ".yaml"} and
                          ("helm" in [x.lower() for x in p.parts] or "k8s" in [x.lower() for x in p.parts]
                           or re.search(r"(?m)^\s*kind:\s*\w+", t))]
        self.all_text = "\n".join(t for _, t in self.files)
        self.java_text = "\n".join(t for _, t in self.java)
        self.build_text = "\n".join(t for _, t in self.build)
        self.config_text = "\n".join(t for _, t in self.config)
        self.manifest_text = "\n".join(t for _, t in self.manifests)
        self.http_client = bool(re.search(r"@FeignClient|\bWebClient\b|\bRestClient\b|\bRestTemplate\b", self.java_text))
        self.messaging = bool(re.search(r"@KafkaListener|KafkaTemplate|RabbitTemplate|@RabbitListener|@JmsListener|JmsTemplate", self.java_text))
        self.external_integration = self.http_client or self.messaging
        self.workload = bool(re.search(r"(?m)^\s*kind:\s*(Deployment|DeploymentConfig|StatefulSet|DaemonSet)\b", self.manifest_text, re.I))
        report_paths = [self.root / "target/site/jacoco/jacoco.xml",
                        self.root / "target/pmd.xml", self.root / "target/cpd.xml",
                        self.root / "target/dependency-check-report.json",
                        self.root / "trivy-report.json"]
        self.reports = [(path, path.read_text(encoding="utf-8", errors="ignore"))
                        for path in report_paths if path.is_file()]
        self.report_text = "\n".join(text for _, text in self.reports)

    def find(self, patterns, groups=None):
        pool = self.files if groups is None else [item for name in groups for item in getattr(self, name)]
        for path, text in pool:
            for pattern in patterns:
                match = re.search(pattern, text, re.I | re.M)
                if match:
                    return {"file": str(path), "line": text.count("\n", 0, match.start()) + 1,
                            "snippet": " ".join(text[match.start():match.end()].split())[:180],
                            "pattern": pattern}
        return None

    def inspected(self, groups=None, limit=12):
        pool = self.files if groups is None else [item for name in groups for item in getattr(self, name)]
        return [str(path) for path, _ in pool[:limit]]

    def foundation(self):
        text = self.build_text
        java = re.search(r"<(?:java\.version|maven\.compiler\.source)>([^<]+)", text)
        spring = re.search(r"<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)", text)
        architecture = "HEXAGONAL" if any(x in str(p).replace("\\", "/").lower() for p, _ in self.java for x in ("port/in", "port/out", "adapter/in", "adapter/out")) else ("LAYERED" if re.search(r"@(RestController|Controller).*@(Service)", self.java_text, re.S) else "UNKNOWN")
        database = next((name for name, pattern in (("PostgreSQL","postgresql"),("MySQL","mysql"),("Oracle","ojdbc"),("MongoDB","mongodb")) if re.search(pattern, self.all_text, re.I)), "Não detectado")
        persistence = "Spring Data JPA" if re.search(r"spring-boot-starter-data-jpa|JpaRepository", self.all_text) else "Não detectada"
        http = "WebClient" if "WebClient" in self.java_text else "Feign" if "@FeignClient" in self.java_text else "RestClient" if "RestClient" in self.java_text else "Não detectado"
        messaging = "Kafka" if re.search(r"Kafka", self.java_text) else "RabbitMQ" if re.search(r"Rabbit", self.java_text) else "Não detectada"
        return {"java": java.group(1).strip() if java else "Não determinado",
                "spring_boot": spring.group(1).strip() if spring else "Não determinado",
                "build": "Maven" if any(p.name == "pom.xml" for p, _ in self.build) else "Gradle" if self.build else "Não determinado",
                "architecture": architecture, "database": database, "persistence": persistence,
                "http_client": http, "messaging": messaging,
                "container": "Docker" if self.docker else "Não encontrado",
                "runtime": "Kubernetes/OpenShift" if self.manifests else "Não determinado"}
