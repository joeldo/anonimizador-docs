from typing import Literal, Protocol

from models.entity import Entity
from models.errors import ApplicationError

DetectionErrorCode = Literal["detector_unavailable", "detection_failed"]


class EntityDetectionError(ApplicationError, RuntimeError):
    def __init__(self, code: DetectionErrorCode) -> None:
        super().__init__(code)


class EntityDetector(Protocol):
    def detect(self, text: str) -> list[Entity]: ...
