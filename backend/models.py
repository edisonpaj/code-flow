from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MethodInfo:
    name: str
    line: int
    end_line: int
    body: str
    mapping: str | None = None
    http_method: str | None = None
    return_type: str = "void"
    parameters: str = ""
    throws: list[str] = field(default_factory=list)


@dataclass
class JavaType:
    name: str
    kind: str
    path: Path
    package: str
    layer: str
    interfaces: list[str] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    methods: list[MethodInfo] = field(default_factory=list)
    base_mapping: str = ""
    annotations: list[str] = field(default_factory=list)
    extends: list[str] = field(default_factory=list)
    source: str = ""
