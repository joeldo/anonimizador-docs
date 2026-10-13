import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult

from detectors.entity_detector import EntityDetectionError, EntityDetector
from detectors.presidio_detector import PresidioDetector, _ADDRESS_PATTERN
from fixtures.gerar_corpus import DESTINO
from models.entity import Entity
from services.pdf_extractor import PdfExtractor
from services.pseudonym_replacer import PseudonymReplacer
from detectors.regex_detector import RegexDetector

pytestmark = pytest.mark.usefixtures("sem_rede")

ADDRESS_CASES = [
    ("Endereco: Rua das Nuvens de Papel, 40, Vila Inventada",
     "Rua das Nuvens de Papel, 40, Vila Inventada"),
    ("Moro na R. Sergipe, 1200, apto 302, Savassi, CEP 30130-170.",
     "R. Sergipe, 1200, apto 302, Savassi"),
    ("Endereco comercial: Av. Afonso Pena 1500 - Centro", "Av. Afonso Pena 1500 - Centro"),
    ("Pç. da Liberdade, 10", "Pç. da Liberdade, 10"),
    ("Rua Aurora, 10; outro texto", "Rua Aurora, 10"),
    ("Fica na Rua Bahia, 55, Centro.", "Rua Bahia, 55, Centro"),
    ("Moro na Rua Bahia, 55 desde 2010", "Rua Bahia, 55"),
    ("Item: servico ficticio. Total: R$ 100,00.", None),
    ("Endereco: Rua sem numero", None),
]


@pytest.mark.parametrize("label", [
    "Endereco", "ENDEREÇO", "Endereço comercial", "Endereço residencial",
    "Logradouro", "Bairro", "Cidade", "Município", "Contratante", "Contratada",
    "Participante", "Candidato", "Candidata", "Remetente", "Destinatário",
    "Destinatária", "Cliente", "Responsável", "Nome", "Testemunha",
])
@pytest.mark.parametrize("entity_type", ["PERSON", "LOCATION"])
def test_descarta_rotulo_seguido_de_dois_pontos(label: str, entity_type: str) -> None:
    analyzer = Mock(spec=AnalyzerEngine)
    analyzer.analyze.return_value = [RecognizerResult(entity_type, 0, len(label), 0.85)]
    assert PresidioDetector(analyzer).detect(f"{label} \t: valor sintetico") == []


@pytest.mark.parametrize(("text", "span"), [
    ("Joao: bom dia", "Joao"),
    ("Endereco sem dois pontos", "Endereco"),
    ("Nome \t", "Nome"),
])
def test_preserva_nome_real_e_span_sem_dois_pontos(text: str, span: str) -> None:
    analyzer = Mock(spec=AnalyzerEngine)
    analyzer.analyze.return_value = [RecognizerResult("PERSON", 0, len(span), 0.85)]
    assert PresidioDetector(analyzer).detect(text) == [Entity("PESSOA", span, 0, len(span))]


@pytest.mark.parametrize(("text", "expected"), ADDRESS_CASES)
def test_regex_endereco_com_flags_presidio(text: str, expected: str | None) -> None:
    pattern = re.compile(_ADDRESS_PATTERN, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    assert [m.group() for m in pattern.finditer(text)] == ([] if expected is None else [expected])


@pytest.fixture(scope="module")
def real_detector() -> PresidioDetector:
    return PresidioDetector()


@pytest.mark.presidio
@pytest.mark.parametrize(("text", "expected"), ADDRESS_CASES)
def test_presidio_real_spans_enderecos(
    real_detector: PresidioDetector, text: str, expected: str | None,
) -> None:
    prefix = "Documento sintetico\n\n"
    entities = real_detector.detect(prefix + text)
    if expected is not None:
        start = (prefix + text).index(expected)
        assert Entity("ENDERECO", expected, start, start + len(expected)) in entities
    else:
        recognizer = PatternRecognizer(
            supported_entity="LOCATION",
            patterns=[Pattern("endereco_brasileiro", _ADDRESS_PATTERN, 0.85)],
        )
        analyzer = Mock(spec=AnalyzerEngine)
        analyzer.analyze.side_effect = lambda text, **kwargs: recognizer.analyze(text, ["LOCATION"])
        assert PresidioDetector(analyzer).detect(text) == []
    assert all("CEP" not in e.texto and "30130-170" not in e.texto
               for e in entities if e.tipo == "ENDERECO")
    if "30130-170" in text:
        start = (prefix + text).index("30130-170")
        assert Entity("CEP", "30130-170", start, start + 9) in RegexDetector().detect(prefix + text)


@pytest.mark.presidio
@pytest.mark.parametrize("path", sorted(DESTINO.glob("*.pdf")), ids=lambda p: p.stem)
def test_corpus_preserva_rotulo_endereco(real_detector: PresidioDetector, path: Path) -> None:
    text = PdfExtractor().extract(path.read_bytes())
    entities = real_detector.detect(text)
    assert not any(e.texto.casefold() == "endereco" for e in entities)
    if path.stem == "contrato":
        markdown = PseudonymReplacer().replace(text, RegexDetector().detect(text) + entities)
        assert "Endereco: [ENDERECO_1]" in markdown


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
