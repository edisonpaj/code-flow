# EXPERT CODE FLOW v0.1

Engenharia reversa local de endpoints Spring Boot com arquitetura hexagonal. Descobre projetos Maven/Gradle, extrai endpoints, resolve interfaces para implementações, segue chamadas por dependências injetadas e gera Mermaid.

## Executar

Windows: execute `start.bat`. Linux/macOS: `chmod +x start.sh && ./start.sh`. Abra `http://127.0.0.1:8000`, informe uma pasta contendo um ou vários projetos e clique em **Carregar**.

## Escopo do MVP

O analisador é estático e propositalmente leve: usa Python e expressões estruturais, sem compilar o Java. Reconhece controllers Spring MVC, mappings, campos injetados, `implements` e os diretórios hexagonais usuais. Sobrecargas, chamadas estáticas, Lombok avançado, reflexão e dispatch condicionado podem exigir evolução do parser.

## API

- `GET /api/projects?root=...`
- `GET /api/endpoints?project=...`
- `GET /api/flow?project=...&endpoint=...`
- `GET /api/health`
- `GET /api/analysis/engines`

## Motor estrutural Spoon + SootUp selecionável

O analisador Java fica isolado em `spoon-analyzer/`. Quando `spoon-hybrid` é
selecionado, Spoon extrai AST, classes, interfaces, records, annotations, campos,
métodos, parâmetros e invocações do código-fonte. Se o projeto já estiver compilado,
SootUp analisa `target/classes` ou `build/classes/...` e acrescenta chamadas de
bytecode, hierarquia de tipos, Control Flow Graph por método e Call Graph CHA.

O Python combina as duas evidências, aplica regras de Spring/Dependency Injection,
classifica a arquitetura e monta o fluxo e o diagrama. Se não existir bytecode,
o modo estrutural continua com Spoon e informa `sootup.state: bytecode_unavailable`.
Se Java ou o JAR estiverem indisponíveis, a requisição usa o motor Python e informa
`fallback_used: true`.

Compile o projeto Spring (`mvn package -DskipTests` ou `gradle classes`) para obter
a análise profunda do SootUp. Compile o analisador uma vez com
`mvn -q -f spoon-analyzer/pom.xml package`. O JAR gerado será
detectado automaticamente. Para desativá-lo, defina `EXPERT_CODE_FLOW_SPOON=off`.
O resultado de `/api/flow` inclui `analysis_engine.active`, `flow_source` e, em
`analysis_engine.spoon.report.sootup`, estado, roots de bytecode, hierarquia, CFGs,
chamadas e Call Graph, deixando explícitas as evidências usadas no fluxo.

## Executar com Docker

```bash
docker build -t expert-code-flow .
docker run --rm -p 8000:8000 expert-code-flow
```

Abra `http://localhost:8000` e valide `http://localhost:8000/api/health`.
O container inclui Python 3.12, Java 17 e o JAR compilado do Spoon + SootUp.

## Publicar no Render

O arquivo `render.yaml` configura o serviço Docker e o health check. Envie este
diretório como raiz de um repositório privado no GitHub. No Render, escolha
**New > Blueprint**, conecte o repositório e aplique o Blueprint encontrado.

Na versão hospedada, use **Pacote ZIP** para enviar o projeto. O diretório local
refere-se ao filesystem do servidor e não ao computador do visitante. Uploads e
caches são temporários por padrão. Para persistir uploads, anexe um disco em
`/app/.uploads`; para manter também os caches, use outro armazenamento adequado.

## Publicar no Cloudflare Containers

O projeto inclui `wrangler.jsonc`, o Worker em `worker/index.ts` e scripts npm para
executar e publicar a imagem Docker no Cloudflare Containers. Consulte o passo a
passo completo em [CLOUDFLARE.md](CLOUDFLARE.md).
