from unittest.mock import Mock

import pytest
from presidio_analyzer import AnalyzerEngine, RecognizerResult

from detectors.entity_detector import EntityDetectionError, EntityDetector
from detectors.presidio_detector import PresidioDetector
from fixtures.gerar_corpus import DESTINO
from models.entity import Entity
from services.pdf_extractor import PdfExtractor

pytestmark = pytest.mark.usefixtures("sem_rede")


def test_presidio_converte_resultados_no_contrato() -> None:
    analyzer = Mock(spec=AnalyzerEngine)
    texto = "Caio Ventobravo; Rua Aurora, 10"
    analyzer.analyze.return_value = [
        RecognizerResult("PERSON", 0, 15, 0.85),
        RecognizerResult("LOCATION", 17, len(texto), 0.85),
    ]
    detector: EntityDetector = PresidioDetector(analyzer=analyzer)
    assert detector.detect(texto) == [
        Entity("PESSOA", texto[:15], 0, 15),
        Entity("ENDERECO", texto[17:], 17, len(texto)),
    ]
    analyzer.analyze.assert_called_once_with(
        text=texto, language="pt", entities=["PERSON", "LOCATION"],
    )


def test_modelo_ausente_nao_dispara_download(monkeypatch: pytest.MonkeyPatch) -> None:
    import detectors.presidio_detector as modulo

    def indisponivel(modelo: str) -> None:
        raise OSError("detalhe privado do ambiente")

    monkeypatch.setattr(modulo.spacy, "load", indisponivel)
    with pytest.raises(EntityDetectionError) as erro:
        PresidioDetector().detect("Texto sintetico")
    assert erro.value.code == "detector_unavailable"
    assert "detalhe privado" not in str(erro.value)


def test_falha_de_analise_e_explicita() -> None:
    analyzer = Mock(spec=AnalyzerEngine)
    analyzer.analyze.side_effect = ValueError("conteudo privado")
    with pytest.raises(EntityDetectionError) as erro:
        PresidioDetector(analyzer=analyzer).detect("Texto sintetico")
    assert erro.value.code == "detection_failed"
    assert "conteudo privado" not in str(erro.value)


def test_linhas_preservam_offsets_globais_e_nao_incluem_rotulos() -> None:
    analyzer = Mock(spec=AnalyzerEngine)
    analyzer.analyze.side_effect = [
        [RecognizerResult("PERSON", 0, 15, 0.85)],
        [RecognizerResult("PERSON", 0, 15, 0.85)],
    ]
    texto = "Caio Ventobravo\n\nCaio Ventobravo"
    entidades = PresidioDetector(analyzer=analyzer).detect(texto)
    assert entidades == [
        Entity("PESSOA", "Caio Ventobravo", 0, 15),
        Entity("PESSOA", "Caio Ventobravo", 17, 32),
    ]
    assert analyzer.analyze.call_count == 2


@pytest.mark.presidio
def test_presidio_real_sem_rede() -> None:
    texto = PdfExtractor().extract((DESTINO / "nota_fiscal_simples.pdf").read_bytes())
    entidades = PresidioDetector().detect(texto)
    for tipo, valor in (
        ("PESSOA", "Bruno Pedraclara"),
        ("ENDERECO", "Rua das Nuvens de Papel, 50, Vila Inventada"),
    ):
        inicio = texto.index(valor)
        assert Entity(tipo, valor, inicio, inicio + len(valor)) in entidades
