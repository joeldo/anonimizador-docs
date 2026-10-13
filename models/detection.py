from typing import Literal

from pydantic import BaseModel, ConfigDict

from models.entity import Entity

DetectorName = Literal["llm", "presidio", "custom"]
FallbackReason = Literal[
    "endpoint_missing", "model_missing", "privacy_blocked",
    "endpoint_unavailable", "timeout", "invalid_response",
]


class DetectionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    detector_used: DetectorName | None = None
    fallback_reason: FallbackReason | None = None


class DetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    entities: list[Entity]
    report: DetectionReport
