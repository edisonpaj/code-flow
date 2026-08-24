import { Container, getContainer } from "@cloudflare/containers";

export interface Env {
  EXPERT_CODE_FLOW: DurableObjectNamespace<ExpertCodeFlowContainer>;
}

/**
 * Executa o FastAPI, o analisador Python e o motor Spoon + SootUp.
 * A porta deve coincidir com o EXPOSE/CMD do Dockerfile.
 */
export class ExpertCodeFlowContainer extends Container {
  defaultPort = 8000;
  requiredPorts = [8000];
  sleepAfter = "2h";
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // O upload devolve caminhos temporários usados nas requisições seguintes.
    // Um nome fixo mantém todo o fluxo na mesma instância do container.
    const container = getContainer(
      env.EXPERT_CODE_FLOW,
      "expert-code-flow-main",
    );

    return container.fetch(request);
  },
} satisfies ExportedHandler<Env>;
