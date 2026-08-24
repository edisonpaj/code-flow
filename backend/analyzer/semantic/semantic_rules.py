SEMANTIC_RULES = {
    ("HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "DELETE", "CALL"): 'Aciona caso de uso "Excluir {entity}"',
    ("HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "CREATE", "CALL"): 'Aciona caso de uso "Criar {entity}"',
    ("HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "UPDATE", "CALL"): 'Aciona caso de uso "Atualizar {entity}"',
    ("HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "READ", "CALL"): 'Aciona caso de uso "Consultar {entity}"',
    ("HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "LIST", "CALL"): 'Aciona caso de uso "Listar {entities}"',
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "DELETE", "FIND"): "Verifica existência do {entity}",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "READ", "FIND"): "Consulta {entity} solicitado",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "UPDATE", "FIND"): "Recupera {entity} para atualização",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "DELETE", "DELETE"): "Solicita remoção do {entity}",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "CREATE", "SAVE"): "Solicita persistência do {entity}",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "UPDATE", "SAVE"): "Solicita persistência das alterações do {entity}",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "LIST", "FIND_ALL"): "Solicita consulta de {entities}",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "READ", "FIND"): "Consulta {entity} no banco",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "DELETE", "FIND"): "Consulta {entity} por identificador",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "UPDATE", "FIND"): "Consulta registro atual do {entity}",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "DELETE", "DELETE"): "Remove registro do {entity}",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "CREATE", "SAVE"): "Insere registro do {entity}",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "UPDATE", "SAVE"): "Atualiza registro do {entity}",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "LIST", "FIND_ALL"): "Consulta registros de {entities}",
}

RELATION_RULES = {
    ("HTTP_ENTRYPOINT", "APPLICATION_SERVICE", "CALL"): "Aciona {operation}",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "FIND"): "Consulta {entity}",
    ("APPLICATION_SERVICE", "PERSISTENCE_ADAPTER", "DELETE"): "Solicita remoção do {entity}",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "FIND"): "Consulta {entity} no banco",
    ("PERSISTENCE_ADAPTER", "DATABASE_REPOSITORY", "DELETE"): "Remove registro do {entity}",
}

OPERATION_FALLBACKS = {"FIND": "Consulta {entity}", "FIND_ALL": "Consulta lista de {entities}",
                       "SAVE": "Persiste {entity}", "DELETE": "Remove {entity}",
                       "UPDATE": "Atualiza {entity}", "VALIDATE": "Valida {entity}"}

RETURN_RULES = {
    ("DATABASE_REPOSITORY", "PERSISTENCE_ADAPTER", "FIND"): "{entity_title} encontrado",
    ("DATABASE_REPOSITORY", "PERSISTENCE_ADAPTER", "FIND_ALL"): "Registros encontrados",
    ("DATABASE_REPOSITORY", "PERSISTENCE_ADAPTER", "DELETE"): "Exclusão concluída",
    ("DATABASE_REPOSITORY", "PERSISTENCE_ADAPTER", "SAVE"): "Persistência concluída",
    ("PERSISTENCE_ADAPTER", "APPLICATION_SERVICE", "DELETE"): "Confirmação da exclusão",
    ("APPLICATION_SERVICE", "HTTP_ENTRYPOINT", "DELETE"): "Exclusão realizada",
}
