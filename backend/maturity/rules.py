"""Catálogo objetivo de maturidade — seis dimensões."""
DIMENSION_WEIGHTS={"CODE_QUALITY":.20,"SOFTWARE_DESIGN":.20,"RESILIENCE":.15,"SECURITY":.20,"OBSERVABILITY":.15,"OPERABILITY":.10}

def rule(i,s,t,e,src,ev,tool="Expert-Code-Flow",applies_when="ALWAYS",score_enabled=True):
    return {"id":i,"subdimension":s,"criterion":t,"evaluates":e,"sources":src,"expected_evidence":ev,"tool":tool,"applies_when":applies_when,"weight":1,"score_enabled":score_enabled,"lifecycle":"ACTIVE"}

QUALITY=[
 rule("QC-STACK-001","Stack & Build","Java suportado","Java declarado é 17 ou 21","pom.xml, .mvn e Dockerfile","Elemento e valor Java","Maven Model / XML Parser"),
 rule("QC-STACK-002","Stack & Build","Spring Boot identificado","Parent ou BOM Spring Boot possui versão","pom.xml","Artifact, versão e origem","Maven Model / XML Parser"),
 rule("QC-BUILD-001","Stack & Build","Maven Wrapper","mvnw, mvnw.cmd e .mvn/wrapper estão presentes","mvnw, mvnw.cmd e .mvn/wrapper","Componentes do wrapper"),
 rule("QC-DEP-001","Stack & Build","Dependências Maven duplicadas","Não há groupId + artifactId repetido","pom.xml","Dependência duplicada","Maven Model"),
 rule("QC-OO-001","Orientação a Objetos","Encapsulamento","Campos de estado não são públicos","Java","Classe, campo e modificador","Spoon"),
 rule("QC-OO-002","Orientação a Objetos","Acoplamento da classe","Número de colaboradores injetados é controlado","Java","Classe e dependências","Spoon"),
 rule("QC-SOLID-DIP-001","SOLID","Dependency Inversion","Dependências apontam para interfaces/ports","Java e type hierarchy","Consumidor, abstração e implementação","Spoon + SootUp"),
 rule("QC-SOLID-SRP-001","SOLID","Sinais de excesso de responsabilidade","Tamanho, métodos, dependências e integrações são controlados","Java","Sinais objetivos","Spoon"),
 rule("QC-SIZE-001","Manutenibilidade","Tamanho da classe","Classe possui no máximo 500 linhas","Java","Classe e linhas","Spoon"),
 rule("QC-SIZE-002","Manutenibilidade","Tamanho do método","Método possui no máximo 80 linhas","Java","Método e linhas","Spoon"),
 rule("QC-COMPLEX-001","Manutenibilidade","Complexidade ciclomática","Complexidade não ultrapassa 15","Relatório PMD","Método, valor e threshold","PMD"),
 rule("QC-DUP-001","Manutenibilidade","Duplicação de código","Não há blocos duplicados relevantes","Relatório PMD CPD","Arquivos e intervalos","PMD CPD"),
 rule("QC-ERR-001","Tratamento de Erros","Global Exception Handler","Existe @RestControllerAdvice com @ExceptionHandler","Java","Classe e handlers","Spoon"),
 rule("QC-ERR-002","Tratamento de Erros","Ausência de printStackTrace","Código não invoca printStackTrace","Java","Arquivo, linha e invocation","Spoon"),
 rule("QC-ERR-003","Tratamento de Erros","Exceções específicas","Exception/RuntimeException genérica é controlada","Java","Catch ou throw genérico","Spoon"),
 rule("QC-TEST-001","Testabilidade","Testes existentes","Existem testes com @Test","src/test/java","Classe e método","Spoon + filesystem"),
 rule("QC-TEST-002","Testabilidade","Testes de integração","Existem @SpringBootTest, @WebMvcTest ou @DataJpaTest","src/test/java","Tipo e annotation","Spoon + filesystem"),
 rule("QC-TEST-003","Testabilidade","Cobertura","JaCoCo informa line e branch coverage","jacoco.xml","Percentuais de cobertura","JaCoCo","JACOCO_REPORT_EXISTS"),]

DESIGN=[
 rule("DS-PATTERN-001","Padrão Arquitetural","Padrão arquitetural detectável","Estrutura e fluxo sustentam a classificação","Código e call graph","Padrão e evidências","Spoon + Expert-Code-Flow"),
 rule("DS-LAYER-001","Separação de Responsabilidades","Fronteiras entre camadas","Controller não acessa persistência diretamente","Código e call graph","Chamada entre camadas","Spoon + Call Graph"),
 rule("DS-DEP-001","Direção das Dependências","Dependências apontam para dentro","Camada interna não depende de implementação externa","Java e hierarchy","Origem, abstração e implementação","Spoon + SootUp"),
 rule("DS-DOM-001","Isolamento do Domínio","Domínio independente de Spring","Domínio não possui stereotypes/imports Spring","domain/**/*.java","Import ou annotation","Spoon"),
 rule("DS-CYCLE-001","Acoplamento","Ausência de ciclos","Grafo não contém ciclo de dependências","Grafo","Caminho do ciclo","SootUp"),
 rule("DS-INT-001","Integrações","Inventário de integrações","Cataloga HTTP, mensageria, banco, Redis e JMS","Código, build e config","Tecnologia, origem e destino","Spoon + Expert-Code-Flow",score_enabled=False),]

RESILIENCE=[
 rule("RES-TIMEOUT-001","Timeout","Timeout por integração HTTP","Cada cliente possui timeout","Java e config","Cliente e timeout","Spoon + config parser","HTTP_CLIENT_EXISTS"),
 rule("RES-CB-001","Circuit Breaker","Circuit Breaker configurado","Integração possui Circuit Breaker","Build, Java e config","Nome e método","Spoon + config parser","EXTERNAL_INTEGRATION_EXISTS"),
 rule("RES-RETRY-001","Retry","Retry configurado","Retry possui tentativas e backoff","Java e config","Método, tentativas e espera","Spoon + config parser","EXTERNAL_INTEGRATION_EXISTS"),
 rule("RES-BULK-001","Bulkhead","Bulkhead configurado","Limite concorrente está configurado","Java e config","Nome e limite","Spoon + config parser","EXTERNAL_INTEGRATION_EXISTS"),
 rule("RES-FALLBACK-001","Fallback / Degradação","Fallback resolvido","fallbackMethod referencia método existente","Java","Annotation e método","Spoon","EXTERNAL_INTEGRATION_EXISTS"),
 rule("RES-MSG-001","Mensageria Resiliente","Dead Letter Queue","Mensageria possui DLQ","Java e config","Recoverer ou destino DLQ","Spoon + config parser","MESSAGING_EXISTS"),
 rule("RES-MSG-002","Mensageria Resiliente","Retry de mensageria","ErrorHandler possui tentativas/backoff","Java e config","Handler e backoff","Spoon + config parser","MESSAGING_EXISTS"),
 rule("RES-MSG-003","Mensageria Resiliente","Idempotência","Há mecanismo explícito de idempotência","Java e persistência","eventId/messageId/inbox","Spoon","MESSAGING_EXISTS"),]

SECURITY=[
 rule("SEC-VAL-001","Validação de Entrada","Bean Validation","Endpoint usa @Valid e DTO possui constraints","Java","Endpoint, DTO e annotations","Spoon"),
 rule("SEC-SECRET-001","Secrets e Credenciais","Secrets externalizados","Não há credencial literal","Java, config, Dockerfile e Helm","Finding mascarado","Gitleaks + parser"),
 rule("SEC-DATA-001","Proteção de Dados","Dados sensíveis não expostos","Responses não expõem campos sensíveis","Java","Response e campo","Spoon"),
 rule("SEC-ERROR-001","Tratamento Seguro de Erros","Exceção não retornada","Resposta não contém exceção/mensagem crua","Java","Handler e corpo","Spoon"),
 rule("SEC-ERROR-002","Tratamento Seguro de Erros","Stack trace não exposto","include-stacktrace não é always","Config","server.error","Config parser"),
 rule("SEC-TLS-001","Segurança das Integrações","TLS nas integrações","Produção não utiliza http://","Java e config","URL e ambiente","Spoon + config parser","EXTERNAL_INTEGRATION_EXISTS"),
 rule("SEC-TLS-002","Segurança das Integrações","Validação TLS habilitada","Código não desabilita certificado/hostname","Java","API insegura","Spoon + Semgrep","EXTERNAL_INTEGRATION_EXISTS"),
 rule("SEC-CVE-001","Dependências Vulneráveis","Sem CVE crítico/alto","Relatório não contém vulnerabilidade crítica/alta sem fix","OWASP/Trivy report","Dependência, CVE, CVSS e fix","OWASP Dependency-Check / Trivy","VULNERABILITY_REPORT_EXISTS"),
 rule("SEC-CONF-001","Configuração Segura","Actuator restrito","Exposure não usa include: *","Config","management.endpoints","Config parser"),
 rule("SEC-CONF-002","Configuração Segura","Debug desabilitado","debug/stacktrace permanente não estão ativos","Config","Configuração insegura","Config parser"),
 rule("SEC-LOG-001","Logging Seguro","Dados sensíveis não logados","Logger não recebe password/token/secret","Java","Linha e argumento mascarado","Spoon"),]

OBSERVABILITY=[
 rule("OBS-HEALTH-001","Health","Actuator Health exposto","Actuator e health estão configurados","Build e config","Dependência e configuração","Build + config parser"),
 rule("OBS-HEALTH-002","Health","HealthIndicator customizado","Existe implementação de HealthIndicator","Java","Classe implementadora","Spoon"),
 rule("OBS-LOG-001","Logging","Logger utilizado","Existe SLF4J Logger ou @Slf4j","Java","Classe e logger","Spoon"),
 rule("OBS-LOG-002","Logging","Logging estruturado","Encoder/layout JSON está configurado","Build, logback e config","Encoder/layout","Config parser"),
 rule("OBS-METRIC-001","Métricas","Micrometer/Prometheus","Dependência exportável está presente","Build e config","Artifact e configuração","Build parser"),
 rule("OBS-METRIC-002","Métricas","Métricas customizadas","MeterRegistry/Counter/Timer/Gauge é usado","Java","Classe e instrumento","Spoon"),
 rule("OBS-TRACE-001","Tracing","Tracing distribuído","Micrometer Tracing/OpenTelemetry está configurado","Build, Java e config","Artifact e versão","Build + config parser"),
 rule("OBS-CORR-001","Correlação","Correlation ID propagado","MDC e header de correlação são usados","Java","MDC key e header","Spoon"),
 rule("OBS-ERR-001","Diagnóstico de Erros","Handlers registram contexto","ExceptionHandler registra trace/correlation/endpoint","Java","Handler, logger e contexto","Spoon"),]

OPERABILITY=[
 rule("OPS-BUILD-001","Build / Empacotamento","Build reproduzível","pom.xml e wrapper estão presentes","Build files","Arquivos encontrados"),
 rule("OPS-BUILD-002","Build / Empacotamento","Artefato versionado","artifactId e version estão declarados","pom.xml","Artifact e versão","Maven Model"),
 rule("OPS-CONT-001","Container","Dockerfile presente","Dockerfile existe","Dockerfile","Arquivo"),
 rule("OPS-CONT-002","Container","Imagem versionada","FROM tem tag fixa diferente de latest","Dockerfile","Imagem e tag"),
 rule("OPS-CONT-003","Container","Build multi-stage","Há estágio de build e runtime","Dockerfile","Estágios FROM"),
 rule("OPS-CONT-004","Container","Execução non-root","USER não-root ou securityContext existe","Dockerfile e manifests","User/securityContext"),
 rule("OPS-K8S-001","Kubernetes / OpenShift","Workload declarado","Deployment/DeploymentConfig existe","Manifests","Kind"),
 rule("OPS-K8S-002","Kubernetes / OpenShift","Service declarado","Service existe","Manifests","Kind Service"),
 rule("OPS-K8S-003","Kubernetes / OpenShift","ConfigMap declarado","ConfigMap existe","Manifests","Kind ConfigMap"),
 rule("OPS-K8S-004","Kubernetes / OpenShift","Secret declarado","Secret existe","Manifests","Kind Secret"),
 rule("OPS-RES-001","Recursos","Requests e limits","CPU/memória possuem requests e limits","Manifests","Quatro configurações"),
 rule("OPS-PROBE-001","Health Operacional","Readiness probe","readinessProbe existe","Manifests","Probe e path"),
 rule("OPS-PROBE-002","Health Operacional","Liveness probe","livenessProbe existe","Manifests","Probe e path"),
 rule("OPS-PROBE-003","Health Operacional","Startup probe","startupProbe existe","Manifests","Probe e path"),
 rule("OPS-SCALE-001","Escalabilidade","Réplicas declaradas","replicas está configurado","Manifests","Quantidade"),
 rule("OPS-SCALE-002","Escalabilidade","HPA declarado","HorizontalPodAutoscaler existe","Manifests","Kind HPA"),
 rule("OPS-SCALE-003","Escalabilidade","Faixa e métrica do HPA","min/maxReplicas e target existem","Manifests","Limites e utilization"),]

DIMENSIONS=[
 {"id":"CODE_QUALITY","name":"Qualidade de Código","question":"A base é sustentável e testável?","description":"Stack, OO, SOLID, manutenção, erros e testes.","criteria":QUALITY},
 {"id":"SOFTWARE_DESIGN","name":"Design de Software","question":"O desenho preserva responsabilidades?","description":"Padrão, camadas, domínio, acoplamento e integrações.","criteria":DESIGN},
 {"id":"RESILIENCE","name":"Resiliência","question":"As integrações degradam de forma controlada?","description":"Timeout, Circuit Breaker, Retry, Bulkhead, fallback e mensageria.","criteria":RESILIENCE},
 {"id":"SECURITY","name":"Segurança","question":"O serviço protege entradas, dados e integrações?","description":"Controles locais; autenticação e autorização pertencem ao API Gateway.","external_controls":{"authentication":"CONTROLLED_EXTERNALLY","authorization":"CONTROLLED_EXTERNALLY","owner":"API Gateway"},"criteria":SECURITY},
 {"id":"OBSERVABILITY","name":"Observabilidade","question":"É possível observar e diagnosticar?","description":"Health, logging, métricas, tracing, correlação e erros.","criteria":OBSERVABILITY},
 {"id":"OPERABILITY","name":"Operabilidade","question":"Pode ser implantado e escalado?","description":"Build, container, Kubernetes/OpenShift, recursos, probes e escala.","criteria":OPERABILITY}]

DIMENSION_NAMES={
 "CODE_QUALITY":"Qualidade de Código",
 "SOFTWARE_DESIGN":"Design de Software",
 "RESILIENCE":"Resiliência",
 "SECURITY":"Segurança",
 "OBSERVABILITY":"Observabilidade",
 "OPERABILITY":"Operabilidade"}
SUBDIMENSION_STRUCTURE={
 "CODE_QUALITY":["Stack & Build","Orientação a Objetos","SOLID","Manutenibilidade","Tratamento de Erros","Testabilidade"],
 "SOFTWARE_DESIGN":["Padrão Arquitetural","Separação de Responsabilidades","Direção das Dependências","Isolamento do Domínio","Acoplamento","Integrações"],
 "RESILIENCE":["Timeout","Circuit Breaker","Retry","Bulkhead","Fallback / Degradação","Mensageria Resiliente"],
 "SECURITY":["Validação de Entrada","Secrets e Credenciais","Proteção de Dados","Tratamento Seguro de Erros","Segurança das Integrações","Dependências Vulneráveis","Configuração Segura","Logging Seguro"],
 "OBSERVABILITY":["Health","Logging","Métricas","Tracing","Correlação","Diagnóstico de Erros"],
 "OPERABILITY":["Build / Empacotamento","Container","Kubernetes / OpenShift","Recursos","Health Operacional","Escalabilidade"]}
for position,dimension in enumerate(DIMENSIONS,1):
    dimension["name"]=DIMENSION_NAMES[dimension["id"]]
    dimension["position"]=position
    dimension["display_code"]=f"{position:02d}"
    dimension["subdimensions"]=SUBDIMENSION_STRUCTURE[dimension["id"]]

def maturity_dimensions_catalog():
    criteria=[r for d in DIMENSIONS for r in d["criteria"]]
    return {"dimensions":DIMENSIONS,"weights":DIMENSION_WEIGHTS,"summary":{"dimensions":len(DIMENSIONS),"subdimensions":sum(len(d["subdimensions"]) for d in DIMENSIONS),"criteria":len(criteria),"scored_criteria":sum(r["score_enabled"] for r in criteria),"version":"1.0-six-dimensions-objective","editable":False,"scoring":"ADHERENT=1; PARTIALLY_ADHERENT=.5; NON_ADHERENT=0; NOT_EVALUATED=0; NOT_APPLICABLE/informational=excluded"}}
