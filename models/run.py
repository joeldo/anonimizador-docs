from typing import Final, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from models.errors import ErrorCode
from models.detection import DetectorName, FallbackReason

MAX_SQLITE_INTEGER: Final = 2**63 - 1


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    id: UUID
    created_at: AwareDatetime
    status: Literal["success", "failure"]
    duration_ms: int = Field(ge=0, le=MAX_SQLITE_INTEGER)
    error_code: ErrorCode | None
    detector_used: DetectorName | None = None
    fallback_reason: FallbackReason | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "RunRecord":
        if (self.status == "success") != (self.error_code is None):
            raise ValueError("Status e codigo de erro incompativeis.")
        if self.fallback_reason is not None and self.detector_used != "presidio":
            raise ValueError("Motivo de fallback exige detector Presidio.")
        return self


class RunPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[RunRecord]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0, le=MAX_SQLITE_INTEGER)
