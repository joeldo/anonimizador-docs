import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import pytest
from reportlab.pdfgen.canvas import Canvas

from detectors.entity_detector import EntityDetectionError, EntityDetector
from fixtures.gerar_corpus import DESTINO, SEED, gerar_cpf
from models.entity import Entity
from services.anonymization_service import AnonymizationService
from services.pdf_extractor import PdfExtractionError

pytestmark = pytest.mark.usefixtures("sem_rede")
DOCUMENTOS = tuple(sorted(DESTINO.glob("*.pdf")))


@pytest.mark.parametrize("caminho", DOCUMENTOS, ids=lambda p: p.stem)
def test_fluxo_com_corpus(caminho: Path, detector_fixture: EntityDetector) -> None:
    markdown = AnonymizationService(detector_fixture).anonymize(caminho.read_bytes())
    gabarito = json.loads(caminho.with_suffix(".json").read_text(encoding="utf-8"))
    for entidade in gabarito["entidades"]:
        if entidade["texto"] in gabarito["cpfs_invalidos"]:
            assert entidade["texto"] in markdown
        else:
            assert entidade["texto"] not in markdown
            assert f"[{entidade['tipo']}_1]" in markdown
    assert markdown.count("[PESSOA_1]") == 2


def test_preserva_consistencia_entre_paginas(detector_fixture: EntityDetector) -> None:
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1)
    for _ in range(2):
        canvas.drawString(40, 780, "Caio Ventobravo")
        canvas.showPage()
    canvas.save()
    markdown = AnonymizationService(detector_fixture).anonymize(buffer.getvalue())
    assert markdown == "[PESSOA_1]\n\n[PESSOA_1]"


def test_servico_concorrente_isola_documentos(detector_fixture: EntityDetector) -> None:
    service = AnonymizationService(detector_fixture)
    documentos = [(DESTINO / nome).read_bytes() for nome in ("contrato.pdf", "ata.pdf")]
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(service.anonymize, documentos))
    assert all("[PESSOA_1]" in resultado and "[PESSOA_2]" not in resultado for resultado in resultados)


def test_nao_chama_detector_se_pdf_invalido() -> None:
    class DetectorNaoUtilizado:
        def detect(self, text: str) -> list[Entity]:
            pytest.fail("Detector nao deve receber PDF invalido.")

    with pytest.raises(PdfExtractionError):
        AnonymizationService(DetectorNaoUtilizado()).anonymize(b"invalido")


def test_nao_entrega_sucesso_se_detector_falhar() -> None:
    class DetectorIndisponivel:
        def detect(self, text: str) -> list[Entity]:
            raise EntityDetectionError("detector_unavailable")

    with pytest.raises(EntityDetectionError):
        AnonymizationService(DetectorIndisponivel()).anonymize(
            (DESTINO / "contrato.pdf").read_bytes()
        )


def test_servico_prioriza_email_sobre_cpf_interno(detector_fixture: EntityDetector) -> None:
    cpf = re.sub(r"\D", "", gerar_cpf(random.Random(SEED)))
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1)
    canvas.drawString(40, 780, f"{cpf}@example.org")
    canvas.showPage()
    canvas.save()
    assert AnonymizationService(detector_fixture).anonymize(buffer.getvalue()) == "[EMAIL_1]"
