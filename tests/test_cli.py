import subprocess
import sys
from pathlib import Path

import pytest

from api import cli
from detectors.entity_detector import EntityDetectionError, EntityDetector
from fixtures.gerar_corpus import DESTINO
from services.anonymization_service import AnonymizationService
from services.pdf_extractor import PdfExtractionError

pytestmark = pytest.mark.usefixtures("sem_rede")


def test_cli_unitaria(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    detector_fixture: EntityDetector,
) -> None:
    monkeypatch.setattr(cli, "create_anonymization_service", lambda: AnonymizationService(detector_fixture))
    assert cli.main([str(DESTINO / "contrato.pdf")]) == 0
    capturado = capsys.readouterr()
    assert "[PESSOA_1]" in capturado.out
    assert "Caio Ventobravo" not in capturado.out
    assert capturado.err == ""


def test_cli_arquivo_inexistente(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([str(tmp_path / "inexistente.pdf")]) == 2
    capturado = capsys.readouterr()
    assert capturado.out == ""
    assert "read_failed" in capturado.err


@pytest.mark.parametrize("erro", [
    PdfExtractionError("invalid_pdf"),
    PdfExtractionError("extraction_failed"),
    EntityDetectionError("detector_unavailable"),
])
def test_cli_erros_nao_produzem_markdown(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    erro: Exception,
) -> None:
    def falhar(self: AnonymizationService, pdf: bytes) -> str:
        raise erro

    monkeypatch.setattr(AnonymizationService, "anonymize", falhar)
    assert cli.main([str(DESTINO / "contrato.pdf")]) != 0
    capturado = capsys.readouterr()
    assert capturado.out == ""
    assert capturado.err


@pytest.mark.presidio
def test_cli_subprocesso_real_sem_rede(subprocess_offline_env: dict[str, str]) -> None:
    resultado = subprocess.run(
        [sys.executable, "-m", "api.cli", str(DESTINO / "nota_fiscal_simples.pdf")],
        capture_output=True, text=True, env=subprocess_offline_env, check=False, timeout=120,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "[PESSOA_1]" in resultado.stdout
    assert "[CPF_1]" in resultado.stdout
    assert "[ENDERECO_1]" in resultado.stdout
    assert "Bruno Pedraclara" not in resultado.stdout
