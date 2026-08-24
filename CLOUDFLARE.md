# Publicação no Cloudflare Containers

## Ambiente publicado

- URL: `https://expert-code-flow.edisonpaj.workers.dev`
- Domínio personalizado: `https://codeflow.eazevedo.com.br`
- Conta Cloudflare: `6db1f6ddaed4f46865305ef9c4c04318`
- Container application: `expert-code-flow-expertcodeflowcontainer`
- Application ID: `a03a3af1-dc68-44a5-8bad-a1a9a5fe328b`
- Instance type: `standard-1`
- Máximo de instâncias: `1`
- Versão inicial: `d5ddbcce-2e79-40c8-b119-43908714b101`

Validação da publicação realizada com sucesso em `/`, `/api/health` e
`/api/analysis/engines`.

## Autenticação MVP

- Tela de entrada: `/login`
- Usuário: `admin`
- Senha: `codeflow`
- Sessão: cookie HttpOnly, SameSite Lax, Secure em HTTPS, válido por 1 hora.
- `/api/health` permanece público para o health check da infraestrutura.
- As demais páginas, arquivos estáticos e APIs exigem autenticação.

As credenciais são propositalmente fixas para o MVP. Antes de disponibilizar o
sistema para múltiplos usuários, substitua-as por segredo de ambiente ou por
Cloudflare Access.

## Componentes incluídos

- Frontend HTML, CSS e JavaScript servido pelo FastAPI.
- Backend FastAPI com Uvicorn.
- Motor de análise Python.
- Java 17 e analisador Spoon + SootUp compilado durante o build Maven.
- Upload seguro de ZIP, geração de PDF e caches temporários.
- Worker Cloudflare roteando todas as chamadas para uma instância estável.

## Pré-requisitos

1. Cloudflare Workers Paid ativo (Containers não está disponível no plano Free).
2. Docker Desktop iniciado.
3. Node.js LTS e npm instalados.

## Validação local da imagem

```powershell
docker build -t expert-code-flow:cloudflare .
docker run --rm -p 8000:8000 --name expert-code-flow expert-code-flow:cloudflare
```

Abra `http://localhost:8000` e valide `http://localhost:8000/api/health`.

## Instalação e autenticação

```powershell
npm install
npx wrangler login
npx wrangler whoami
```

## Desenvolvimento local com o Worker

```powershell
npm run cf:dev
```

Abra a URL informada pelo Wrangler, normalmente `http://localhost:8787`.

## Publicação

```powershell
npm run cf:deploy
```

No primeiro deploy, o Worker pode responder antes de o container terminar de ser
provisionado. Aguarde alguns minutos se as primeiras chamadas falharem.

## Operação

```powershell
npm run cf:status
npm run cf:images
npm run cf:logs
```

Também é possível acompanhar o serviço em **Workers & Pages > Containers**.

## Limitações importantes

- Na internet, use **Pacote ZIP**. Um caminho como `D:\\projetos` pertence à
  máquina do visitante e não pode ser lido pelo servidor na Cloudflare.
- O disco do container é efêmero. Uploads e caches desaparecem quando a instância
  é recriada. Para persistência futura, mova os artefatos para Cloudflare R2.
- A configuração usa `standard-1` (4 GiB) para comportar Python, JVM, Spoon,
  SootUp e projetos Java extraídos. Monitore consumo antes de reduzir a instância.
- Todas as chamadas usam uma instância nomeada porque upload, descoberta,
  endpoints, fluxo, maturidade e relatório compartilham caminhos temporários.
- Proteja a aplicação com Cloudflare Access antes de receber código-fonte real.

## Domínio próprio

No Dashboard, abra o Worker e acesse **Settings > Domains & Routes > Add >
Custom Domain**. O HTTPS é provisionado automaticamente pela Cloudflare.
