import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from pydantic import ValidationError

from detectors.entity_detector import EntityDetectionError, EntityDetector
from detectors.regex_detector import RegexDetector
from detectors.llm_detector import FallbackDetector, LlmDetector, ReportedDetectionError
from models.detection import DetectionReport, DetectionResult
from models.errors import ApplicationError
from models.run import RunRecord
from models.settings import get_settings
from repositories.run_repository import RunRepository
from services.pdf_extractor import PdfExtractor
from services.privacy_logging import sensitive_processing
from services.pseudonym_replacer import PseudonymReplacer, ReplacementError

logger = logging.getLogger("anonimizador_pdf")


class AnonymizationService:
    def __init__(
        self,
        entity_detector: EntityDetector,
        extractor: PdfExtractor | None = None,
        regex_detector: RegexDetector | None = None,
        replacer: PseudonymReplacer | None = None,
        repository: RunRepository | None = None,
    ) -> None:
        self._entity_detector = entity_detector
        self._extractor = extractor if extractor is not None else PdfExtractor()
        self._regex_detector = regex_detector if regex_detector is not None else RegexDetector()
        self._replacer = replacer if replacer is not None else PseudonymReplacer()
        self._repository = repository if repository is not None else RunRepository(get_settings().runs_db_path)

    def anonymize(self, pdf: bytes) -> str:
        started = perf_counter()
        run_id = uuid4()
        created_at = datetime.now(timezone.utc)
        report = DetectionReport()
        try:
            with sensitive_processing():
                texto = self._extractor.extract(pdf)
                try:
                    regex_entities = self._regex_detector.detect(texto)
                    result = self._detect(texto)
                    report = result.report
                    markdown = self._replacer.replace(texto, regex_entities + result.entities)
                except ValidationError:
                    raise ReplacementError() from None
        except ApplicationError as error:
            if isinstance(error, ReportedDetectionError):
                report = error.report
            self._record(RunRecord(
                id=run_id, created_at=created_at, status="failure",
                duration_ms=int((perf_counter() - started) * 1000), error_code=error.code,
                detector_used=report.detector_used, fallback_reason=report.fallback_reason,
            ))
            logger.warning("run_failed id=%s error_code=%s", run_id, error.code)
            raise
        self._record(RunRecord(
            id=run_id, created_at=created_at, status="success",
            duration_ms=int((perf_counter() - started) * 1000), error_code=None,
            detector_used=report.detector_used, fallback_reason=report.fallback_reason,
        ))
        logger.info("run_completed id=%s status=success detector=%s fallback_reason=%s",
                    run_id, report.detector_used, report.fallback_reason)
        return markdown

    def _detect(self, texto: str) -> DetectionResult:
        from detectors.presidio_detector import PresidioDetector

        try:
            if isinstance(self._entity_detector, FallbackDetector):
                return self._entity_detector.detect_with_report(texto)
            return DetectionResult(
                entities=self._entity_detector.detect(texto),
                report=DetectionReport(detector_used=(
                    "presidio" if isinstance(self._entity_detector, PresidioDetector) else "custom"
                )),
            )
        except ApplicationError:
            raise
        except ValidationError:
            raise
        except (ValueError, RuntimeError, OSError):
            raise EntityDetectionError("detection_failed") from None

    def _record(self, run: RunRecord) -> None:
        try:
            self._repository.add(run)
        except ApplicationError as error:
            logger.error("run_persistence_failed id=%s error_code=%s", run.id, error.code)
            raise


def create_anonymization_service(repository: RunRepository | None = None) -> AnonymizationService:
    from detectors.presidio_detector import PresidioDetector

    return AnonymizationService(
        FallbackDetector(LlmDetector(get_settings()), PresidioDetector()), repository=repository,
    )
