from enum import Enum
from pydantic import BaseModel, Field


class CapacityStatus(str, Enum):
    HEALTHY = "HEALTHY"
    ADEQUATE = "ADEQUATE"
    ATTENTION = "ATTENTION"
    POTENTIAL_BOTTLENECK = "POTENTIAL_BOTTLENECK"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CapacityInput(BaseModel):
    project_path: str
    target_tps: float = Field(gt=0)
    average_response_time_ms: float = Field(gt=0)
    headroom_percent: float = Field(default=30, ge=0, le=500)
    endpoint: str | None = None
