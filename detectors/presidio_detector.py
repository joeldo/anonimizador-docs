from threading import Lock

import spacy
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NerModelConfiguration, SpacyNlpEngine
from presidio_analyzer.predefined_recognizers import SpacyRecognizer

from detectors.entity_detector import EntityDetectionError
from models.entity import Entity, EntityType
from services.privacy_logging import sensitive_processing

_ENTITY_TYPES: dict[str, EntityType] = {"PERSON": "PESSOA", "LOCATION": "ENDERECO"}
_ADDRESS_PATTERN = (
    r"\b(?:Rua|Avenida|Av\.|Travessa|Alameda|Praca|Praça|Estrada|Rodovia)"
    r"[ \t]+[^\n,;]+,[ \t]*[0-9]+(?:[ \t]*,[ \t]*[^\n;]+)?"
)


def _create_analyzer() -> AnalyzerEngine:
    try:
        modelo = spacy.load("pt_core_news_lg")
        engine = SpacyNlpEngine(
            models=[{"lang_code": "pt", "model_name": "pt_core_news_lg"}],
            ner_model_configuration=NerModelConfiguration(
                labels_to_ignore=["ORG", "MISC"],
                model_to_presidio_entity_mapping={"PER": "PERSON", "LOC": "LOCATION"},
                low_score_entity_names=[],
            ),
        )
        # O carregamento explicito evita o download automatico do SpacyNlpEngine.
        engine.nlp = {"pt": modelo}
        registry = RecognizerRegistry(
            supported_languages=["pt"],
            recognizers=[
                SpacyRecognizer(supported_language="pt", supported_entities=["PERSON", "LOCATION"]),
                PatternRecognizer(
                    supported_entity="LOCATION",
                    supported_language="pt",
                    patterns=[Pattern("endereco_brasileiro", _ADDRESS_PATTERN, 0.85)],
                    name="BrazilianAddressRecognizer",
                ),
            ],
        )
        return AnalyzerEngine(
            registry=registry,
            nlp_engine=engine,
            supported_languages=["pt"],
            log_decision_process=False,
        )
    except (OSError, ValueError, RuntimeError):
        raise EntityDetectionError("detector_unavailable") from None


class PresidioDetector:
    def __init__(self, analyzer: AnalyzerEngine | None = None) -> None:
        self._analyzer = analyzer
        self._lock = Lock()

    @sensitive_processing()
    def detect(self, text: str) -> list[Entity]:
        with self._lock:
            if self._analyzer is None:
                self._analyzer = _create_analyzer()
            entidades: list[Entity] = []
            offset = 0
            for linha in text.splitlines(keepends=True):
                conteudo = linha.rstrip("\r\n")
                if conteudo.strip():
                    try:
                        results = self._analyzer.analyze(
                            text=conteudo, language="pt", entities=["PERSON", "LOCATION"],
                        )
                    except (OSError, ValueError, RuntimeError):
                        raise EntityDetectionError("detection_failed") from None
                    for result in results:
                        if (
                            result.entity_type not in _ENTITY_TYPES
                            or not 0 <= result.start < result.end <= len(conteudo)
                        ):
                            raise EntityDetectionError("detection_failed")
                        entidades.append(Entity(
                            _ENTITY_TYPES[result.entity_type], conteudo[result.start:result.end],
                            offset + result.start, offset + result.end,
                        ))
                offset += len(linha)
            return entidades
