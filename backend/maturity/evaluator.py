from __future__ import annotations

import re

from .rules import DIMENSIONS, DIMENSION_WEIGHTS
from .scanner import ScanContext
from .scoring import consolidate_dimensions, dimension_score


def _result(rule, status, reason, ctx, evidence=None, groups=None, missing=None):
    processing_status = "NOT_EVALUATED" if status == "NOT_EVALUATED" else "EVALUATED"
    result = {"PASS": "ADHERENT", "PARTIAL": "PARTIALLY_ADHERENT", "FAIL": "NON_ADHERENT",
              "NOT_APPLICABLE": "NOT_APPLICABLE"}.get(status)
    points = {"ADHERENT": 1.0, "PARTIALLY_ADHERENT": .5, "NON_ADHERENT": 0.0}.get(result)
    confidence = .98 if evidence else .90 if status in {"PASS", "FAIL"} else .70 if status == "PARTIAL" else 0.0
    normalized_evidence = ({**evidence, "symbol": evidence.get("symbol"),
                            "finding": evidence.get("finding") or evidence.get("snippet", "")}
                           if evidence else None)
    return {**rule, "criterionId": rule["id"], "processing_status": processing_status,
            "status": result or processing_status, "result": result, "score": points,
            "confidence": confidence, "reason": reason,
            "evidence": [normalized_evidence] if normalized_evidence else [], "inspected_files": ctx.inspected(groups),
            "missing_evidence": missing or [], "evaluator": "OBJECTIVE_MVP_0.2"}


def _positive(rule, ctx, patterns, groups=None, missing=None):
    found = ctx.find(patterns, groups)
    return _result(rule, "PASS" if found else "FAIL",
                   "Evidência objetiva encontrada" if found else "Evidência obrigatória não encontrada",
                   ctx, found, groups, [] if found else (missing or patterns))


def _negative(rule, ctx, patterns, groups=None, partial=False):
    found = ctx.find(patterns, groups)
    return _result(rule, "PARTIAL" if found and partial else "FAIL" if found else "PASS",
                   "Padrão de risco encontrado" if found else "Nenhum padrão de risco encontrado",
                   ctx, found, groups)


def _applicability(rule, ctx):
    condition = rule["applies_when"]
    if condition == "EXTERNAL_INTEGRATION_EXISTS" and not ctx.external_integration:
        return _result(rule, "NOT_APPLICABLE", "Regra avaliada: nenhuma integração externa foi identificada; esta proteção não se aplica ao contexto encontrado", ctx, groups=["java", "config", "build"])
    if condition == "HTTP_CLIENT_EXISTS" and not ctx.http_client:
        return _result(rule, "NOT_APPLICABLE", "Nenhum cliente HTTP foi encontrado", ctx)
    if condition == "SECURITY_CONTEXT_KNOWN" and not re.search(r"spring-security|SecurityFilterChain|oauth2", ctx.all_text, re.I):
        return _result(rule, "NOT_EVALUATED", "Segurança pode estar delegada a gateway ou infraestrutura externa", ctx)
    if condition == "DOCKERFILE_EXISTS" and not ctx.docker:
        return _result(rule, "NOT_EVALUATED", "Dockerfile não foi encontrado no escopo analisado", ctx)
    if condition == "MANIFESTS_EXIST" and not ctx.manifests:
        return _result(rule, "NOT_EVALUATED", "Manifests Kubernetes/OpenShift/Helm não foram encontrados no escopo", ctx)
    if condition == "WORKLOAD_EXISTS" and not ctx.workload:
        return _result(rule, "NOT_EVALUATED", "Deployment ou workload equivalente não foi encontrado", ctx)
    if condition == "MESSAGING_EXISTS" and not ctx.messaging:
        return _result(rule, "NOT_APPLICABLE", "Nenhuma integração de mensageria foi encontrada", ctx)
    if condition == "JACOCO_REPORT_EXISTS" and not any(p.name == "jacoco.xml" for p, _ in ctx.reports):
        return _result(rule, "NOT_EVALUATED", "Relatório JaCoCo não encontrado; cobertura não foi inferida", ctx)
    if condition == "VULNERABILITY_REPORT_EXISTS" and not any(
            p.name in {"dependency-check-report.json", "trivy-report.json"} for p, _ in ctx.reports):
        return _result(rule, "NOT_EVALUATED", "Relatório OWASP Dependency-Check/Trivy não encontrado", ctx)
    return None


def _evaluate(rule, ctx):
    applicable = _applicability(rule, ctx)
    if applicable: return applicable
    rid = rule["id"]
    aliases={"QC-STACK-001":"MAINT-JAVA-001","QC-STACK-002":"MAINT-SPRING-001",
             "QC-DEP-001":"MAINT-DUP-001","QC-OO-001":"OO-ENC-001",
             "QC-SOLID-DIP-001":"SOLID-DIP-001","DS-PATTERN-001":"ARCH-PATTERN-001",
             "DS-LAYER-001":"SOLID-LAYER-001","DS-DEP-001":"SOLID-DIP-001",
             "DS-DOM-001":"SOLID-DOM-001"}
    rid=aliases.get(rid,rid)
    if rule["id"] == "QC-BUILD-001":
        required=[ctx.root/"mvnw",ctx.root/"mvnw.cmd",ctx.root/".mvn/wrapper"]
        missing=[str(p.relative_to(ctx.root)) for p in required if not p.exists()]
        evidence=next(({"file":str(p),"line":1,"snippet":p.name,"pattern":"Maven Wrapper"} for p in required if p.exists()),None)
        return _result(rule,"PASS" if not missing else "FAIL","Maven Wrapper completo" if not missing else "Componentes do Maven Wrapper ausentes",ctx,evidence,missing=missing)
    if rule["id"] == "QC-OO-002":
        maximum=0;owner=None
        for path,text in ctx.java:
            count=len(re.findall(r"private\s+final\s+[A-Z]\w*(?:<[^;>]+>)?\s+\w+\s*;",text))
            if count>maximum: maximum,owner=count,path
        status="PASS" if maximum<=5 else "PARTIAL"
        evidence={"file":str(owner),"line":1,"snippet":f"{maximum} colaboradores injetados","pattern":"campos private final"} if owner else None
        return _result(rule,status,f"Maior acoplamento encontrado: {maximum} colaboradores",ctx,evidence,["java"])
    if rule["id"] == "QC-SOLID-SRP-001":
        signals=[];evidence=None
        for path,text in ctx.java:
            count=text.count("\n")+1;methods=len(re.findall(r"\b(public|protected|private)\s+[\w<>?,.\[\]]+\s+\w+\s*\(",text));deps=len(re.findall(r"private\s+final\s+",text))
            if count>500 or methods>20 or deps>7:
                signals.append(f"{path.name}: {count} linhas, {methods} métodos, {deps} dependências")
                evidence={"file":str(path),"line":1,"snippet":signals[-1],"pattern":"heurística SRP"};break
        return _result(rule,"PARTIAL" if signals else "PASS",signals[0] if signals else "Nenhum sinal objetivo de excesso de responsabilidade",ctx,evidence,["java"])
    if rule["id"] in {"QC-SIZE-001","QC-SIZE-002"}:
        if rule["id"]=="QC-SIZE-001":
            found=next(((p,t.count("\n")+1) for p,t in ctx.java if t.count("\n")+1>500),None);limit=500
        else:
            found=None;limit=80
            method_re=re.compile(r"(?m)^\s*(?:public|private|protected)\s+[^;{}]+\{",re.M)
            for p,t in ctx.java:
                for m in method_re.finditer(t):
                    depth=0;end=m.end()
                    for pos in range(m.end()-1,len(t)):
                        depth += (t[pos]=="{")-(t[pos]=="}")
                        if depth==0: end=pos;break
                    lines=t.count("\n",m.start(),end)+1
                    if lines>80: found=(p,lines);break
                if found: break
        evidence={"file":str(found[0]),"line":1,"snippet":f"{found[1]} linhas; limite {limit}","pattern":"tamanho"} if found else None
        return _result(rule,"PARTIAL" if found else "PASS",f"Limite de {limit} linhas "+("excedido" if found else "respeitado"),ctx,evidence,["java"])
    if rule["id"] in {"QC-COMPLEX-001","QC-DUP-001"}:
        report_name="pmd.xml" if rule["id"]=="QC-COMPLEX-001" else "cpd.xml"
        report=next(((p,t) for p,t in ctx.reports if p.name==report_name),None)
        if not report:return _result(rule,"NOT_EVALUATED",f"Relatório {report_name} não encontrado",ctx)
        risk=bool(re.search(r"violation|duplication|<duplication",report[1],re.I))
        evidence={"file":str(report[0]),"line":1,"snippet":"Finding presente no relatório" if risk else "Relatório sem findings","pattern":report_name}
        return _result(rule,"PARTIAL" if risk else "PASS","Finding encontrado" if risk else "Nenhum finding encontrado",ctx,evidence)
    if rule["id"] == "QC-ERR-001":
        advice=ctx.find([r"@RestControllerAdvice",r"@ControllerAdvice"],["java"]);handler=ctx.find([r"@ExceptionHandler"],["java"])
        return _result(rule,"PASS" if advice and handler else "FAIL","Handler global completo" if advice and handler else "@RestControllerAdvice e @ExceptionHandler não foram encontrados em conjunto",ctx,advice or handler,["java"])
    if rule["id"] == "QC-ERR-002": return _negative(rule,ctx,[r"\.printStackTrace\s*\("],["java"])
    if rule["id"] == "QC-ERR-003": return _negative(rule,ctx,[r"catch\s*\(\s*Exception\b",r"throw\s+new\s+RuntimeException\b"],["java"],True)
    if rule["id"] in {"QC-TEST-001","QC-TEST-002"}:
        patterns=[r"@Test\b"] if rule["id"]=="QC-TEST-001" else [r"@(SpringBootTest|WebMvcTest|DataJpaTest)\b"]
        found=None
        for p,t in ctx.test_java:
            m=re.search(patterns[0],t)
            if m: found={"file":str(p),"line":t.count("\n",0,m.start())+1,"snippet":m.group(),"pattern":patterns[0]};break
        return _result(rule,"PASS" if found else "FAIL","Teste encontrado" if found else "Teste esperado não encontrado",ctx,found)
    if rule["id"] == "QC-TEST-003":
        report=next(((p,t) for p,t in ctx.reports if p.name=="jacoco.xml"),None)
        counters=re.findall(r'<counter type="(LINE|BRANCH)" missed="(\d+)" covered="(\d+)"',report[1]) if report else []
        values={kind:round(int(covered)*100/(int(missed)+int(covered))) for kind,missed,covered in counters if int(missed)+int(covered)}
        evidence={"file":str(report[0]),"line":1,"snippet":str(values),"pattern":"JaCoCo counter"} if report else None
        return _result(rule,"PASS" if values.get("LINE",0)>=80 else "PARTIAL",f"Cobertura: {values}",ctx,evidence)
    if rid == "ENG-MAVEN-001":
        wrapper=next((p for p,_ in ctx.files if p.name.lower() in {"mvnw","mvnw.cmd"}),None)
        evidence={"file":str(wrapper),"line":1,"snippet":wrapper.name,"pattern":"Maven Wrapper"} if wrapper else None
        return _result(rule,"PASS" if wrapper else "FAIL","Maven Wrapper encontrado" if wrapper else "Maven Wrapper não encontrado",ctx,evidence)
    if rid == "ARCH-PATTERN-001":
        architecture=ctx.foundation()["architecture"]
        if architecture == "UNKNOWN": return _result(rule,"NOT_EVALUATED","O padrão arquitetural não pôde ser determinado com evidência suficiente",ctx,groups=["java"])
        evidence=ctx.find([r"package\s+[^;]*(adapter|port|controller|service|repository)",r"@(RestController|Controller|Service|Repository)"],["java"])
        return _result(rule,"PASS",f"Padrão {architecture} detectado por packages e stereotypes",ctx,evidence,["java"])
    if rid == "ARCH-RES-001":
        timeout=ctx.find([r"connectTimeout",r"readTimeout",r"responseTimeout",r"timeout-duration"],None)
        protection=ctx.find([r"@CircuitBreaker",r"resilience4j\.circuitbreaker",r"@Retry\b",r"resilience4j\.retry",r"@Bulkhead",r"resilience4j\.bulkhead"],None)
        status="PASS" if timeout and protection else "PARTIAL" if timeout or protection else "FAIL"
        reason="Timeout e proteção de resiliência encontrados" if status=="PASS" else "Proteções de integração parcialmente configuradas" if status=="PARTIAL" else "Timeout e proteção de resiliência não encontrados"
        return _result(rule,status,reason,ctx,timeout or protection,None,[name for name,value in (("timeout explícito",timeout),("Circuit Breaker, Retry ou Bulkhead",protection)) if not value])
    if rid == "SOLID-DIP-001":
        services = [(p,t) for p,t in ctx.java if re.search(r"@Service|/service/", str(p).replace("\\","/"), re.I)]
        if not services: return _result(rule,"NOT_EVALUATED","Nenhum Service foi identificado",ctx)
        bad = next(((p,t) for p,t in services if re.search(r"private\s+final\s+\w*(RepositoryImpl|Adapter)\b",t)),None)
        good = next(((p,t) for p,t in services if re.search(r"private\s+final\s+\w*(Port|UseCase|Repository)\b",t)),None)
        return _result(rule,"FAIL" if bad else "PASS" if good else "NOT_EVALUATED","Dependência concreta encontrada" if bad else "Dependência por abstração encontrada" if good else "Tipo da dependência não foi conclusivo",ctx,ctx.find([r"private\s+final\s+\w*(Port|UseCase|Repository|Adapter)\b"], ["java"]))
    if rid == "SOLID-CTRL-001":
        controllers=[(p,t) for p,t in ctx.java if re.search(r"@(RestController|Controller)",t)]
        if not controllers:return _result(rule,"NOT_EVALUATED","Nenhum Controller identificado",ctx)
        bad=next(((p,t) for p,t in controllers if re.search(r"private\s+final\s+\w*(JpaRepository|Repository|PersistenceAdapter)\b",t)),None)
        return _result(rule,"FAIL" if bad else "PASS","Controller acessa persistência diretamente" if bad else "Nenhum acesso direto do Controller à persistência",ctx,ctx.find([r"private\s+final\s+\w*(JpaRepository|Repository|PersistenceAdapter)\b"],["java"]))
    if rid == "SOLID-DOM-001":
        domain=[(p,t) for p,t in ctx.java if "domain" in [x.lower() for x in p.parts]]
        if not domain:return _result(rule,"NOT_EVALUATED","Package de domínio não identificado",ctx)
        found=next(((p,t) for p,t in domain if re.search(r"@(Service|Repository|RestController|Component|Configuration)\b",t)),None)
        return _negative(rule,ctx,[r"@(Service|Repository|RestController|Component|Configuration)\b"],["java"]) if found else _result(rule,"PASS","Domínio sem stereotypes Spring",ctx,groups=["java"])
    if rid == "SOLID-LAYER-001":
        bad=ctx.find([r"@(RestController|Controller)[\s\S]{0,1500}private\s+final\s+\w*(JpaRepository|PersistenceAdapter)\b"],["java"])
        return _result(rule,"PARTIAL" if bad else "PASS","Cruzamento de camada detectado" if bad else "Fronteiras principais respeitadas",ctx,bad,["java"])
    if rule["id"] == "DS-CYCLE-001":
        graph={}
        for path,text in ctx.java:
            owner_match=re.search(r"\b(?:class|interface)\s+(\w+)",text)
            if owner_match: graph[owner_match.group(1)]=set(re.findall(r"private\s+(?:final\s+)?([A-Z]\w+)\s+\w+\s*;",text))
        cycle=None
        def visit(node,path):
            nonlocal cycle
            if node in path: cycle=path[path.index(node):]+[node];return
            for target in graph.get(node,set()):
                if target in graph and not cycle: visit(target,path+[node])
        for node in graph:
            if not cycle:visit(node,[])
        evidence={"file":"call-graph","line":1,"snippet":" → ".join(cycle),"pattern":"dependency cycle"} if cycle else None
        return _result(rule,"FAIL" if cycle else "PASS","Ciclo detectado" if cycle else "Nenhum ciclo detectado",ctx,evidence,["java"])
    if rule["id"] == "DS-INT-001":
        technologies=[name for name,pattern in (("WebClient",r"\bWebClient\b"),("RestClient",r"\bRestClient\b"),("Feign",r"@FeignClient"),("RestTemplate",r"\bRestTemplate\b"),("Kafka",r"KafkaTemplate|@KafkaListener"),("JMS",r"JmsTemplate|@JmsListener"),("Redis",r"RedisTemplate"),("Repository",r"JpaRepository|CrudRepository")) if re.search(pattern,ctx.all_text)]
        evidence={"file":"inventário estrutural","line":1,"snippet":", ".join(technologies) or "Nenhuma integração","pattern":"integration inventory"}
        return _result(rule,"PASS","Integrações catalogadas: "+(", ".join(technologies) or "nenhuma"),ctx,evidence)
    if rule["id"] == "RES-FALLBACK-001":
        annotation=ctx.find([r"fallbackMethod\s*=\s*\"(\w+)\""],["java"])
        if not annotation:return _result(rule,"FAIL","fallbackMethod não encontrado",ctx,groups=["java"])
        name=re.search(r'fallbackMethod\s*=\s*"(\w+)"',annotation["snippet"]).group(1)
        method=ctx.find([rf"\b{re.escape(name)}\s*\("],["java"])
        return _result(rule,"PASS" if method else "FAIL","Método fallback resolvido" if method else "Método fallback não existe",ctx,method or annotation,["java"])
    if rule["id"] == "RES-MSG-001": return _positive(rule,ctx,[r"DeadLetterPublishingRecoverer",r"dead[-_.]?letter|\.DLQ\b"],None)
    if rule["id"] == "RES-MSG-002": return _positive(rule,ctx,[r"DefaultErrorHandler",r"FixedBackOff|ExponentialBackOff"],None)
    if rule["id"] == "RES-MSG-003":
        found=ctx.find([r"eventId|messageId|processed_events|Idempotency-Key|\bInbox\b"],None)
        return _result(rule,"PASS" if found else "NOT_EVALUATED","Mecanismo explícito encontrado" if found else "Idempotência não pôde ser comprovada",ctx,found)
    if rule["id"] == "SEC-DATA-001":
        found=ctx.find([r"ResponseEntity\s*<\s*\w*(Entity|JpaEntity)\b",r"ResponseEntity[\s\S]{0,300}\b(password|token|secret|cpf|cardNumber)\b"],["java"])
        return _result(rule,"PARTIAL" if found else "PASS","Possível exposição de dado sensível" if found else "Exposição direta não encontrada",ctx,found,["java"])
    if rule["id"] == "SEC-ERROR-001": return _negative(rule,ctx,[r"\.body\s*\(\s*(e|exception|throwable)(\.getMessage\s*\(\s*\))?\s*\)"],["java"])
    if rule["id"] == "SEC-ERROR-002": return _negative(rule,ctx,[r"include-stacktrace\s*[:=]\s*always"],["config"])
    if rule["id"] == "SEC-TLS-001": return _negative(rule,ctx,[r"http://(?!localhost|127\.0\.0\.1)"],None,True)
    if rule["id"] == "SEC-TLS-002": return _negative(rule,ctx,[r"InsecureTrustManagerFactory|NoopHostnameVerifier|trustAll|disableSslValidation"],None)
    if rule["id"] == "SEC-CVE-001":
        report=next(((p,t) for p,t in ctx.reports if p.name in {"dependency-check-report.json","trivy-report.json"}),None)
        high=bool(report and re.search(r'"severity"\s*:\s*"(HIGH|CRITICAL)"',report[1],re.I))
        evidence={"file":str(report[0]),"line":1,"snippet":"HIGH/CRITICAL encontrado" if high else "Sem HIGH/CRITICAL","pattern":"vulnerability severity"}
        return _result(rule,"FAIL" if high else "PASS","Vulnerabilidade alta/crítica encontrada" if high else "Relatório sem vulnerabilidade alta/crítica",ctx,evidence)
    if rule["id"] == "SEC-CONF-001": return _negative(rule,ctx,[r"include\s*[:=]\s*[\"']?\*[\"']?"],["config"])
    if rule["id"] == "SEC-CONF-002": return _negative(rule,ctx,[r"(?m)^\s*debug\s*[:=]\s*true",r"include-stacktrace\s*[:=]\s*always"],["config"])
    if rule["id"] == "SEC-LOG-001": return _negative(rule,ctx,[r"log(?:ger)?\.(?:info|debug|warn|error)\s*\([^\n;]*(password|senha|token|secret)"],["java"])
    if rule["id"] == "OBS-HEALTH-001":
        actuator=ctx.find([r"spring-boot-starter-actuator"],["build"]);health=ctx.find([r"include\s*[:=][^\n]*(health|\*)",r"management\.endpoint\.health"],["config"])
        return _result(rule,"PASS" if actuator and health else "PARTIAL" if actuator or health else "FAIL","Actuator e health configurados" if actuator and health else "Configuração de health incompleta",ctx,actuator or health)
    if rule["id"] == "OBS-HEALTH-002": return _positive(rule,ctx,[r"implements\s+HealthIndicator"],["java"])
    if rule["id"] == "OBS-LOG-001": return _positive(rule,ctx,[r"@Slf4j\b",r"LoggerFactory\.getLogger"],["java"])
    if rule["id"] == "OBS-LOG-002": return _positive(rule,ctx,[r"logstash-logback|LogstashEncoder|JsonLayout|JsonEncoder"],None)
    if rule["id"] == "OBS-METRIC-002": return _positive(rule,ctx,[r"\bMeterRegistry\b",r"\b(Counter|Timer|Gauge)\.builder"],["java"])
    if rule["id"] == "OBS-CORR-001":
        mdc=ctx.find([r"MDC\.put\s*\([^)]*(correlation|trace)"],["java"]);header=ctx.find([r"X-Correlation-Id|correlationId"],["java"])
        return _result(rule,"PASS" if mdc and header else "PARTIAL" if mdc or header else "FAIL","Correlação e propagação encontradas" if mdc and header else "Correlação incompleta",ctx,mdc or header,["java"])
    if rule["id"] == "OBS-ERR-001":
        handler=ctx.find([r"@ExceptionHandler"],["java"]);logging=ctx.find([r"log(?:ger)?\.(error|warn)[^;]*(traceId|correlationId|endpoint|exception)"],["java"])
        return _result(rule,"PASS" if handler and logging else "PARTIAL" if handler else "FAIL","Handler registra contexto" if handler and logging else "Diagnóstico de erro incompleto",ctx,logging or handler,["java"])
    if rid == "OO-ENC-001": return _negative(rule,ctx,[r"(?m)^\s*public\s+(?!class|interface|record|static)[\w<>?,.\[\]]+\s+\w+\s*;"],["java"])
    if rid == "OO-BEH-001":
        domain=[t for p,t in ctx.java if "domain" in [x.lower() for x in p.parts]]
        if not domain:return _result(rule,"NOT_EVALUATED","Classes de domínio não identificadas",ctx)
        methods=re.findall(r"\b(?:public|protected)\s+\w[\w<>?,.]*\s+(\w+)\s*\(","\n".join(domain))
        business=[m for m in methods if not re.match(r"^(get|set|is|equals|hashCode|toString)",m,re.I)]
        return _result(rule,"PASS" if business else "PARTIAL","Comportamento de domínio encontrado" if business else "Domínio predominantemente anêmico",ctx,ctx.find([rf"\b{re.escape(business[0])}\s*\("] ,["java"]) if business else None,["java"])
    if rid == "OO-CTOR-001":
        dependencies=re.findall(r"private\s+(final\s+)?([A-Z]\w+)\s+\w+\s*;",ctx.java_text)
        if not dependencies:return _result(rule,"NOT_APPLICABLE","Nenhuma dependência por campo identificada",ctx)
        ratio=sum(bool(final) for final,_ in dependencies)/len(dependencies)
        return _result(rule,"PASS" if ratio==1 else "PARTIAL" if ratio>=.5 else "FAIL",f"{round(ratio*100)}% das dependências identificadas são final",ctx,groups=["java"])
    if rid == "OO-HER-001":
        extends=dict(re.findall(r"class\s+(\w+)\s+extends\s+(\w+)",ctx.java_text))
        depth=0
        for child in extends:
            seen=set();cur=child;value=0
            while cur in extends and cur not in seen:seen.add(cur);cur=extends[cur];value+=1
            depth=max(depth,value)
        return _result(rule,"FAIL" if depth>2 else "PASS",f"Profundidade máxima de herança detectada: {depth}",ctx,groups=["java"])
    positive={
      "SEC-VAL-001":([r"@Valid(?=\s|\()",r"@(NotNull|NotBlank|Size|Pattern|Email)(?=\s|\()"],["java"]),
      "SEC-SPRING-001":([r"spring-boot-starter-security",r"SecurityFilterChain",r"oauth2ResourceServer"],None),
      "SEC-AUTHZ-001":([r"@PreAuthorize",r"authorizeHttpRequests",r"@Secured"],["java"]),
      "PERF-PAGE-001":([r"\b(Pageable|Page<|Slice<)",r"\.limit\("],["java"]),
      "RES-TIMEOUT-001":([r"connectTimeout",r"readTimeout",r"responseTimeout",r"timeout-duration"],None),
      "RES-CB-001":([r"@CircuitBreaker",r"resilience4j\.circuitbreaker"],None),
      "RES-RETRY-001":([r"@Retry\b",r"resilience4j\.retry",r"RetryTemplate"],None),
      "RES-BULK-001":([r"@Bulkhead",r"resilience4j\.bulkhead"],None),
      "OBS-ACT-001":([r"spring-boot-starter-actuator"],["build"]),
      "OBS-HEALTH-001":([r"management\..*health",r"HealthIndicator",r"show-details"],None),
      "OBS-METRIC-001":([r"micrometer",r"prometheus",r"MeterRegistry"],None),
      "OBS-TRACE-001":([r"micrometer-tracing",r"opentelemetry",r"spring-cloud-starter-sleuth"],None),
      "OBS-LOG-001":([r"logstash-logback",r"JsonLayout",r"MDC\.put",r"%X\{"],None),
      "MAINT-SPRING-001":([r"spring-boot-starter-parent[\s\S]{0,150}<version>[^<$]",r"org\.springframework\.boot"],["build"]),
    }
    if rid in positive:
        patterns,groups=positive[rid];return _positive(rule,ctx,patterns,groups)
    negative={
      "SEC-SECRET-001":[r"(?i)(password|passwd|secret|api[-_]?key|token)\s*[:=]\s*['\"]?(?!\$\{|\{\{|<|ENC\()[^\s'\"]{5,}"],
      "SEC-ERROR-001":[r"printStackTrace\s*\(",r"ResponseEntity[^\n]*(Exception|Throwable)"],
      "PERF-ALL-001":[r"findAll\s*\(\)\s*\.\s*(stream|forEach)"],
      "PERF-LOOP-001":[r"(?s)(for\s*\(|\.forEach\s*\().{0,500}(repository|Repository)\."],
      "MAINT-SNAPSHOT-001":[r"<version>[^<]*SNAPSHOT</version>"],
      "MAINT-EXC-001":[r"catch\s*\(\s*(Exception|Throwable)\b",r"catch\s*\([^)]*\)\s*\{\s*\}",r"printStackTrace\s*\("],
    }
    if rid in negative:return _negative(rule,ctx,negative[rid],None,rid=="PERF-LOOP-001")
    if rid == "PERF-HTTP-001":
        reused=ctx.find([r"private\s+final\s+(WebClient|RestClient|RestTemplate)",r"@Bean[\s\S]{0,300}(WebClient|RestClient|RestTemplate)"],["java"])
        timeout=ctx.find([r"connectTimeout",r"readTimeout",r"responseTimeout"],None)
        return _result(rule,"PASS" if reused and timeout else "PARTIAL" if reused or timeout else "FAIL","Cliente reutilizado e timeout encontrados" if reused and timeout else "Configuração HTTP incompleta",ctx,reused or timeout,None,[x for x,v in (("cliente reutilizado",reused),("timeout explícito",timeout)) if not v])
    if rule["id"] == "OPS-BUILD-001":
        pom=ctx.root/"pom.xml";wrapper=[ctx.root/"mvnw",ctx.root/"mvnw.cmd",ctx.root/".mvn/wrapper"]
        ok=pom.exists() and all(p.exists() for p in wrapper)
        evidence={"file":str(pom),"line":1,"snippet":"pom.xml + Maven Wrapper","pattern":"reproducible build"} if pom.exists() else None
        return _result(rule,"PASS" if ok else "FAIL","Build reproduzível completo" if ok else "pom.xml ou Maven Wrapper incompleto",ctx,evidence,missing=[str(p.relative_to(ctx.root)) for p in [pom,*wrapper] if not p.exists()])
    if rule["id"] == "OPS-BUILD-002":
        artifact=ctx.find([r"<artifactId>[^<$][^<]*</artifactId>"],["build"]);version=ctx.find([r"<version>[^<$][^<]*</version>"],["build"])
        return _result(rule,"PASS" if artifact and version else "FAIL","Artifact e versão encontrados" if artifact and version else "Artifact/version incompleto",ctx,artifact or version,["build"])
    if rule["id"] == "OPS-CONT-001":
        return _result(rule,"PASS" if ctx.docker else "FAIL","Dockerfile encontrado" if ctx.docker else "Dockerfile não encontrado",ctx,ctx.find([r"(?m)^FROM\s+"],["docker"]) if ctx.docker else None,["docker"])
    if rule["id"] == "OPS-CONT-002":
        fixed=ctx.find([r"(?m)^FROM\s+[^\s:]+:(?!latest\b)[^\s]+"],["docker"]);latest=ctx.find([r"(?m)^FROM\s+[^\s:]+(?::latest)?\s*$"],["docker"])
        return _result(rule,"PASS" if fixed and not latest else "FAIL","Imagem possui tag fixa" if fixed and not latest else "Imagem ausente, sem tag ou latest",ctx,fixed or latest,["docker"])
    if rule["id"] == "OPS-CONT-003": return _positive(rule,ctx,[r"(?m)^FROM\s+.+\s+AS\s+|^FROM\s+[\s\S]*^FROM\s+"],["docker"])
    if rule["id"] == "OPS-CONT-004":
        found=ctx.find([r"(?m)^USER\s+(?!root\b)\S+",r"runAsNonRoot\s*:\s*true"],None)
        return _result(rule,"PASS" if found else "FAIL","Execução non-root configurada" if found else "USER/securityContext non-root não encontrado",ctx,found)
    ops_manifest_patterns={"OPS-K8S-001":r"kind:\s*(Deployment|DeploymentConfig)","OPS-K8S-002":r"kind:\s*Service\b","OPS-K8S-003":r"kind:\s*ConfigMap\b","OPS-K8S-004":r"kind:\s*Secret\b","OPS-PROBE-001":r"readinessProbe\s*:","OPS-PROBE-002":r"livenessProbe\s*:","OPS-PROBE-003":r"startupProbe\s*:","OPS-SCALE-001":r"(?m)^\s*replicas\s*:\s*\d+","OPS-SCALE-002":r"kind:\s*HorizontalPodAutoscaler\b"}
    if rule["id"] in ops_manifest_patterns:
        if not ctx.manifests:return _result(rule,"NOT_EVALUATED","Manifests Kubernetes/OpenShift não encontrados",ctx)
        return _positive(rule,ctx,[ops_manifest_patterns[rule["id"]]],["manifests"])
    if rule["id"] == "OPS-RES-001":
        patterns=[r"(?s)requests:.*?cpu:",r"(?s)requests:.*?memory:",r"(?s)limits:.*?cpu:",r"(?s)limits:.*?memory:"]
        found=[ctx.find([p],["manifests"]) for p in patterns];count=sum(bool(x) for x in found)
        return _result(rule,"PASS" if count==4 else "PARTIAL" if count else "FAIL",f"{count}/4 configurações de recursos encontradas",ctx,next((x for x in found if x),None),["manifests"])
    if rule["id"] == "OPS-SCALE-003":
        parts=[ctx.find([p],["manifests"]) for p in (r"minReplicas\s*:\s*\d+",r"maxReplicas\s*:\s*\d+",r"averageUtilization\s*:\s*\d+")];count=sum(bool(x) for x in parts)
        return _result(rule,"PASS" if count==3 else "PARTIAL" if count else "FAIL",f"{count}/3 parâmetros do HPA encontrados",ctx,next((x for x in parts if x),None),["manifests"])
    if rid == "IAC-DOCKER-001":
        version=ctx.find([r"(?m)^FROM\s+[^\s:]+:[^\s]+"],["docker"]);nonroot=ctx.find([r"(?m)^USER\s+(?!root\b)\S+"],["docker"])
        return _result(rule,"PASS" if version and nonroot else "PARTIAL" if version or nonroot else "FAIL","Imagem versionada e usuário non-root" if version and nonroot else "Dockerfile parcialmente seguro",ctx,version or nonroot,["docker"],[x for x,v in (("imagem versionada",version),("USER non-root",nonroot)) if not v])
    if rid == "IAC-MULTI-001": return _positive(rule,ctx,[r"(?m)^FROM\s+.+\s+AS\s+|^FROM\s+[\s\S]*^FROM\s+"],["docker"])
    if rid == "IAC-WORKLOAD-001": return _positive(rule,ctx,[r"(?m)^\s*kind:\s*(Deployment|DeploymentConfig)\b"],["manifests"])
    if rid in {"IAC-PROBE-001","IAC-RESOURCE-001","IAC-NET-001"}:
        pairs={"IAC-PROBE-001":([r"readinessProbe:"],[r"livenessProbe:"]),"IAC-RESOURCE-001":([r"(?s)requests:.*?(cpu|memory):"],[r"(?s)limits:.*?(cpu|memory):"]),"IAC-NET-001":([r"kind:\s*Service"],[r"kind:\s*(ConfigMap|Secret)"])}
        a=ctx.find(pairs[rid][0],["manifests"]);b=ctx.find(pairs[rid][1],["manifests"])
        return _result(rule,"PASS" if a and b else "PARTIAL" if a or b else "FAIL","Conjunto completo encontrado" if a and b else "Evidência parcial encontrada" if a or b else "Evidência não encontrada",ctx,a or b,["manifests"])
    if rid == "E2E-JAVA-DOCKER-001":
        build_match=re.search(r"<(?:java\.version|maven\.compiler\.source)>\s*(\d+)",ctx.build_text,re.I)
        docker_match=re.search(r"^FROM\s+[^\s:]+:(?:[^\s]*?)(\d{2})(?:\D|$)","\n".join(t for _,t in ctx.docker),re.I|re.M)
        if not build_match or not docker_match:
            return _result(rule,"NOT_EVALUATED","Não foi possível determinar simultaneamente as versões Java do build e da imagem",ctx,groups=["build","docker"])
        build_java,docker_java=build_match.group(1),docker_match.group(1)
        evidence=ctx.find([r"(?m)^FROM\s+.*"],["docker"])
        return _result(rule,"PASS" if build_java==docker_java else "FAIL",f"Java do build {build_java}; Java da imagem {docker_java}",ctx,evidence,["build","docker"])
    if rid == "E2E-PORT-001":
        app_match=re.search(r"^\s*server\.port\s*[=:]\s*(\d+)|^\s*port:\s*(\d+)",ctx.config_text,re.I|re.M)
        service_match=re.search(r"^\s*targetPort:\s*(\d+)",ctx.manifest_text,re.I|re.M)
        if not app_match or not service_match:
            return _result(rule,"NOT_EVALUATED","server.port ou targetPort numérico não foi encontrado para comparação",ctx,groups=["config","manifests"])
        app_port=next(x for x in app_match.groups() if x);service_port=service_match.group(1)
        return _result(rule,"PASS" if app_port==service_port else "FAIL",f"Porta da aplicação {app_port}; targetPort {service_port}",ctx,ctx.find([r"targetPort:\s*\d+"],["manifests"]),["config","manifests"])
    if rid == "E2E-PROBE-001":
        paths=re.findall(r"^\s*path:\s*([^\s#]+)",ctx.manifest_text,re.I|re.M)
        health_paths=[p for p in paths if re.search(r"health|ready|live",p,re.I)]
        if not paths:return _result(rule,"NOT_EVALUATED","Nenhum path HTTP de probe foi encontrado",ctx,groups=["manifests"])
        return _result(rule,"PASS" if len(health_paths)>=2 else "PARTIAL" if health_paths else "FAIL",f"{len(health_paths)} de {len(paths)} paths de probe relacionados a health/readiness/liveness",ctx,ctx.find([r"path:\s*[^\s#]+"],["manifests"]),["config","manifests"])
    if rid == "E2E-HPA-001":
        hpa=ctx.find([r"(?m)^\s*kind:\s*HorizontalPodAutoscaler\b"],["manifests"])
        if not hpa:return _result(rule,"NOT_APPLICABLE","Nenhum HPA foi declarado; a relação resources ↔ HPA não se aplica",ctx,groups=["manifests"])
        requests=ctx.find([r"(?s)requests:.*?(cpu|memory):"],["manifests"])
        return _result(rule,"PASS" if requests else "FAIL","HPA possui resources.requests de referência" if requests else "HPA encontrado sem resources.requests",ctx,requests or hpa,["manifests"])
    if rid == "MAINT-JAVA-001":
        found=ctx.find([r"<(java\.version|maven\.compiler\.source)>\s*(17|21)\s*</",r"sourceCompatibility\s*=\s*['\"]?(17|21)"],["build"])
        declared=ctx.find([r"<(java\.version|maven\.compiler\.source)>\s*([^<]+)</",r"sourceCompatibility"],["build"])
        return _result(rule,"PASS" if found else "FAIL" if declared else "NOT_EVALUATED","Java suportado (17/21)" if found else "Versão Java fora da política" if declared else "Política/versão Java não determinada",ctx,found or declared,["build"])
    if rid == "MAINT-DUP-001":
        deps=re.findall(r"<dependency>[\s\S]*?<groupId>([^<]+)</groupId>[\s\S]*?<artifactId>([^<]+)</artifactId>[\s\S]*?</dependency>",ctx.build_text)
        dup=next((d for d in deps if deps.count(d)>1),None)
        return _result(rule,"FAIL" if dup else "PASS","Dependência duplicada: "+":".join(dup) if dup else "Nenhuma dependência duplicada",ctx,groups=["build"])
    if rid == "MAINT-SIZE-001":
        oversized=next(((p,t) for p,t in ctx.java if t.count("\n")+1>500),None)
        long_method=ctx.find([r"(?s)\b(public|private|protected)\b[^{};]+\{(?:[^{}]|\{[^{}]*\}){2500,}\}"],["java"])
        return _result(rule,"PARTIAL" if oversized or long_method else "PASS","Classe/método acima do limite MVP" if oversized or long_method else "Tamanhos dentro dos limites MVP",ctx,long_method,["java"])
    return _result(rule,"NOT_EVALUATED","A regra não produziu evidência conclusiva",ctx)


def evaluate_dimension(project_path: str, dimension_id: str):
    ctx=ScanContext(project_path);dimension=next((d for d in DIMENSIONS if d["id"]==dimension_id),None)
    if not dimension: raise ValueError("Dimensão não encontrada")
    results=[{**_evaluate(rule,ctx),"dimension":dimension_id} for rule in dimension["criteria"]]
    score,coverage,conf,evaluated,applicable=dimension_score(results)
    statuses={"ADHERENT":sum(r["result"]=="ADHERENT" for r in results),
              "PARTIALLY_ADHERENT":sum(r["result"]=="PARTIALLY_ADHERENT" for r in results),
              "NON_ADHERENT":sum(r["result"]=="NON_ADHERENT" for r in results),
              "NOT_APPLICABLE":sum(r["result"]=="NOT_APPLICABLE" for r in results),
              "NOT_EVALUATED":sum(r["processing_status"]=="NOT_EVALUATED" for r in results)}
    statuses.update({"total":len(results),"evaluated":len(results)-statuses["NOT_EVALUATED"],
                     "evaluated_applicable":evaluated,"applicable":applicable})
    subdimensions=[]
    for name in dict.fromkeys(r["subdimension"] for r in results):
        subset=[r for r in results if r["subdimension"]==name]
        sub_score,sub_coverage,sub_conf,sub_evaluated,sub_applicable=dimension_score(subset)
        subdimensions.append({"name":name,"score":sub_score,"coverage_percent":sub_coverage,
                              "confidence":sub_conf,"evaluated":sub_evaluated,
                              "applicable":sub_applicable,"criteria":len(subset)})
    return {"dimension_id":dimension_id,"dimension":dimension["name"],"score":score,
            "coverage_percent":coverage,"confidence":conf,"criteria":results,"summary":statuses,
            "subdimensions":subdimensions,
            "foundation":ctx.foundation(),"weight":DIMENSION_WEIGHTS[dimension_id],
            "external_controls":dimension.get("external_controls",{}),
            "scoring":{"ADHERENT":1,"PARTIALLY_ADHERENT":.5,"NON_ADHERENT":0,
                       "NOT_EVALUATED":0,"excluded":["NOT_APPLICABLE"]}}


def consolidate(results):
    score,coverage,conf,evaluated,applicable=consolidate_dimensions(results)
    foundation=next((r.get("foundation") for r in results if r.get("foundation")),{})
    return {"score":score,"coverage_percent":coverage,"confidence":conf,
            "evaluated_criteria":evaluated,"applicable_criteria":applicable,
            "not_evaluated_criteria":sum(r["summary"]["NOT_EVALUATED"] for r in results),
            "not_applicable_criteria":sum(r["summary"]["NOT_APPLICABLE"] for r in results),
            "dimensions":results,"foundation":foundation,"weights":DIMENSION_WEIGHTS,
            "method":"SIX_DIMENSIONS_OBJECTIVE_MODEL_1.0"}
