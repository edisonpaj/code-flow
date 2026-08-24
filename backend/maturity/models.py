from dataclasses import dataclass, field


@dataclass
class Evidence:
    file: str
    line: int
    snippet: str
    pattern: str


@dataclass
class RuleResult:
    id: str
    processing_status: str
    result: str | None
    score: float | None
    reason: str
    evidence: list[dict] = field(default_factory=list)
    inspected_files: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
