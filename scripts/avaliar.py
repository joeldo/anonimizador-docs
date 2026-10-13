import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from detectors.entity_detector import EntityDetector
from detectors.presidio_detector import PresidioDetector
from detectors.regex_detector import RegexDetector, is_valid_cpf
from models.entity import ENTITY_TYPES, Entity, EntityType
from models.errors import ApplicationError
from services.pdf_extractor import PdfExtractor
from services.privacy_logging import sensitive_processing
from services.pseudonym_replacer import select_entities

CORPUS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "corpus"


class ExpectedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    tipo: EntityType
    texto: str = Field(min_length=1, repr=False)


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    documento: str
    seed: int
    sintetico: bool
    entidades: list[ExpectedEntity]
    cpfs_invalidos: list[str]


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tipo: EntityType
    tp: int = Field(ge=0)
    fp: int = Field(ge=0)
    fn: int = Field(ge=0)
    precisao: float | None
    recall: float | None


class Report(BaseModel):
    documentos: int
    cpfs_invalidos_excluidos: int
    metricas: list[Metrics]


def _metrics(tipo: EntityType, tp: int, fp: int, fn: int) -> Metrics:
    return Metrics(
        tipo=tipo, tp=tp, fp=fp, fn=fn,
        precisao=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
    )


def score_entities(expected: Sequence[Entity], predicted: Sequence[Entity]) -> list[Metrics]:
    metricas: list[Metrics] = []
    for tipo in ENTITY_TYPES:
        verdade = {e for e in expected if e.tipo == tipo}
        deteccoes = {e for e in predicted if e.tipo == tipo}
        metricas.append(_metrics(
            tipo, len(verdade & deteccoes), len(deteccoes - verdade), len(verdade - deteccoes),
        ))
    return metricas


def _expected_entities(text: str, answer: Answer) -> tuple[list[Entity], int]:
    if any(is_valid_cpf(cpf) for cpf in answer.cpfs_invalidos):
        raise ApplicationError("invalid_corpus")
    entities: list[Entity] = []
    cursor = 0
    excluidos = 0
    for expected in answer.entidades:
        inicio = text.find(expected.texto, cursor)
        if inicio < 0:
            raise ApplicationError("invalid_corpus")
        cursor = inicio + len(expected.texto)
        if expected.tipo == "CPF" and expected.texto in answer.cpfs_invalidos:
            excluidos += 1
        else:
            entities.append(Entity(expected.tipo, expected.texto, inicio, cursor))
    if excluidos != len(answer.cpfs_invalidos):
        raise ApplicationError("invalid_corpus")
    return entities, excluidos


@sensitive_processing()
def evaluate_corpus(corpus: Path, detector: EntityDetector) -> Report:
    pdfs = sorted(corpus.glob("*.pdf"))
    if not pdfs or {p.stem for p in pdfs} != {p.stem for p in corpus.glob("*.json")}:
        raise ApplicationError("invalid_corpus")
    totais: dict[EntityType, list[int]] = {tipo: [0, 0, 0] for tipo in ENTITY_TYPES}
    excluidos = 0
    extractor = PdfExtractor()
    regex = RegexDetector()
    for pdf in pdfs:
        try:
            answer = Answer.model_validate_json(pdf.with_suffix(".json").read_text(encoding="utf-8"))
            if answer.documento != pdf.name:
                raise ApplicationError("invalid_corpus")
            text = extractor.extract(pdf.read_bytes())
            expected, invalidos = _expected_entities(text, answer)
            predicted = select_entities(text, regex.detect(text) + detector.detect(text))
        except (OSError, UnicodeError, ValidationError):
            raise ApplicationError("invalid_corpus") from None
        excluidos += invalidos
        for metrics in score_entities(expected, predicted):
            counts = totais[metrics.tipo]
            counts[0] += metrics.tp
            counts[1] += metrics.fp
            counts[2] += metrics.fn
    return Report(
        documentos=len(pdfs), cpfs_invalidos_excluidos=excluidos,
        metricas=[_metrics(tipo, *totais[tipo]) for tipo in ENTITY_TYPES],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avaliar deteccao local contra gabaritos JSON.")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args(argv)
    try:
        report = evaluate_corpus(args.corpus, PresidioDetector())
    except ApplicationError as error:
        sys.stderr.write(f"{error.code}: {error.message}\n")
        return 1
    print(f"PDFs: {report.documentos} | CPFs invalidos excluidos: {report.cpfs_invalidos_excluidos}")
    print(f"{'TIPO':<10} {'TP':>4} {'FP':>4} {'FN':>4} {'PRECISAO':>10} {'RECALL':>10}")
    for metrics in report.metricas:
        precisao = "N/A" if metrics.precisao is None else f"{metrics.precisao:.4f}"
        recall = "N/A" if metrics.recall is None else f"{metrics.recall:.4f}"
        print(f"{metrics.tipo:<10} {metrics.tp:>4} {metrics.fp:>4} {metrics.fn:>4} {precisao:>10} {recall:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
