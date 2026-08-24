from enum import Enum


class OperationKind(str, Enum):
    CALL = "CALL"
    FIND = "FIND"
    FIND_ALL = "FIND_ALL"
    SAVE = "SAVE"
    DELETE = "DELETE"
    UPDATE = "UPDATE"
    VALIDATE = "VALIDATE"
    PUBLISH = "PUBLISH"
    CONSUME = "CONSUME"
    UNKNOWN = "UNKNOWN"


OPERATION_MAPPINGS = [
    {"patterns": ["findAll", "listar", "list"], "operation_kind": "FIND_ALL"},
    {"patterns": ["find*", "buscar*", "consultar*", "get*"], "operation_kind": "FIND"},
    {"patterns": ["save*", "salvar*", "persist*", "insert*", "create*", "cadastrar*"], "operation_kind": "SAVE"},
    {"patterns": ["delete*", "excluir*", "remover*", "remove*"], "operation_kind": "DELETE"},
    {"patterns": ["update*", "atualizar*", "alterar*"], "operation_kind": "UPDATE"},
    {"patterns": ["valid*", "validate*", "exists*", "existe*"], "operation_kind": "VALIDATE"},
    {"patterns": ["publish*", "publicar*", "send*"], "operation_kind": "PUBLISH"},
    {"patterns": ["consume*", "consumir*", "receive*"], "operation_kind": "CONSUME"},
    {"patterns": ["fallback"], "operation_kind": "CALL"},
]


def classify_operation(method_name: str) -> OperationKind:
    name = (method_name or "").lower()
    if name in {"findall", "listar", "list"}: return OperationKind.FIND_ALL
    if name.startswith(("find", "buscar", "consultar", "get")): return OperationKind.FIND
    if name.startswith(("save", "salvar", "persist", "insert", "create", "cadastrar")): return OperationKind.SAVE
    if name.startswith(("delete", "excluir", "remover", "remove")): return OperationKind.DELETE
    if name.startswith(("update", "atualizar", "alterar")): return OperationKind.UPDATE
    if name.startswith(("valid", "validate", "exists", "existe")): return OperationKind.VALIDATE
    if name.startswith(("publish", "publicar", "send")): return OperationKind.PUBLISH
    if name.startswith(("consume", "consumir", "receive")): return OperationKind.CONSUME
    return OperationKind.CALL
