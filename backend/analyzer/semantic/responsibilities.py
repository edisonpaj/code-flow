ARCHITECTURAL_RESPONSIBILITIES = {
    "HTTP_ENTRYPOINT": {"name": "API", "responsibility": "Receber requisição HTTP, tratar o contrato, acionar o caso de uso e devolver resposta."},
    "APPLICATION_SERVICE": {"name": "Serviço de Aplicação", "responsibility": "Orquestrar o caso de uso e coordenar domínio, persistência e integrações."},
    "USE_CASE_PORT": {"name": "Porta de Entrada", "responsibility": "Representar uma operação disponibilizada pela aplicação."},
    "PERSISTENCE_PORT": {"name": "Porta de Persistência", "responsibility": "Expressar uma necessidade de acesso a dados da aplicação."},
    "PERSISTENCE_ADAPTER": {"name": "Persistência", "responsibility": "Traduzir operações da aplicação para a tecnologia de persistência."},
    "DATABASE_REPOSITORY": {"name": "Banco de Dados", "responsibility": "Executar operações concretas de leitura e gravação."},
    "DOMAIN_OBJECT": {"name": "Domínio", "responsibility": "Executar comportamento e regras de domínio."},
    "HTTP_CLIENT": {"name": "Integração HTTP", "responsibility": "Consumir serviço externo via HTTP."},
    "MESSAGE_PRODUCER": {"name": "Publicador", "responsibility": "Publicar evento ou comando."},
    "MESSAGE_CONSUMER": {"name": "Consumidor", "responsibility": "Receber e processar evento ou comando."},
    "UNKNOWN": {"name": "Componente", "responsibility": "Sem classificação suficiente."},
}
