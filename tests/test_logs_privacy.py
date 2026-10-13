import json
import logging
from collections.abc import Sequence

import pytest
from pypdf import PdfReader

from detectors.entity_detector import EntityDetectionError, EntityDetector
from fixtures.gerar_corpus import DESTINO
from models.entity import Entity
from services.anonymization_service import AnonymizationService
from services.pdf_extractor import PdfExtractionError

pytestmark = pytest.mark.usefixtures("sem_rede")


def assert_logs_sem_texto_dos_pdfs(records: Sequence[logging.LogRecord]) -> None:
    proibidos: set[str] = set()
    for caminho in DESTINO.glob("*.pdf"):
        reader = PdfReader(caminho)
        texto = "\n".join(p.extract_text() for p in reader.pages)
        proibidos.add(texto)
        proibidos.update(linha.strip() for linha in texto.splitlines() if len(linha.strip()) >= 12)
        gabarito = json.loads(caminho.with_suffix(".json").read_text(encoding="utf-8"))
        proibidos.update(e["texto"] for e in gabarito["entidades"])
    for record in records:
        mensagem = logging.Formatter().format(record)
        assert not any(valor in mensagem for valor in proibidos), "Log contem texto de fixture."


def test_detector_de_vazamento_realmente_falha() -> None:
    record = logging.LogRecord("teste", logging.INFO, "", 0, "Caio Ventobravo", (), None)
    with pytest.raises(AssertionError, match="Log contem texto"):
        assert_logs_sem_texto_dos_pdfs([record])


def test_logs_debug_de_sucesso_e_falha_nao_contem_texto(
    caplog: pytest.LogCaptureFixture, detector_fixture: EntityDetector,
) -> None:
    caplog.set_level(logging.DEBUG)
    service = AnonymizationService(detector_fixture)
    for pdf in sorted(DESTINO.glob("*.pdf")):
        service.anonymize(pdf.read_bytes())
    with pytest.raises(PdfExtractionError):
        service.anonymize(b"%PDF-1.7\nCaio Ventobravo\n")
    assert_logs_sem_texto_dos_pdfs(caplog.records[:])
    assert any(r.getMessage().startswith("run_completed") for r in caplog.records)
    assert any(r.getMessage().startswith("run_failed") for r in caplog.records)


@pytest.mark.presidio
def test_logs_presidio_real_em_debug_nao_contem_texto(caplog: pytest.LogCaptureFixture) -> None:
    from services.anonymization_service import create_anonymization_service

    caplog.set_level(logging.DEBUG)
    create_anonymization_service().anonymize((DESTINO / "nota_fiscal_simples.pdf").read_bytes())
    assert_logs_sem_texto_dos_pdfs(caplog.records[:])


def test_excecao_e_logs_de_detector_externo_nao_vazam(caplog: pytest.LogCaptureFixture) -> None:
    segredo = "CREDENCIAL-SINTETICA-NAO-REGISTRAR"

    class DetectorComErro:
        def detect(self, text: str) -> list[Entity]:
            try:
                raise ValueError(text)
            except ValueError:
                logging.getLogger("detector.externo").exception(
                    "Falha de detector credencial=%s correspondencia=%s",
                    segredo, {"[PESSOA_1]": "Caio Ventobravo"},
                )
                raise

    caplog.set_level(logging.DEBUG)
    with pytest.raises(EntityDetectionError) as erro:
        AnonymizationService(DetectorComErro()).anonymize(
            (DESTINO / "contrato.pdf").read_bytes()
        )
    assert erro.value.code == "detection_failed"
    assert_logs_sem_texto_dos_pdfs(caplog.records[:])
    assert segredo not in caplog.text
    assert "[PESSOA_1]" not in caplog.text
