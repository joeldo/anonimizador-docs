import json
import random
import re
from pathlib import Path

import pytest

from detectors.regex_detector import RegexDetector, _ENDERECO, is_valid_cnpj, is_valid_cpf
from fixtures.gerar_corpus import DESTINO, SEED, gerar_cnpj, gerar_cpf, invalidar_cpf
from models.entity import Entity
from services.pdf_extractor import PdfExtractor

pytestmark = pytest.mark.usefixtures("sem_rede")
DOCUMENTOS = tuple(sorted(DESTINO.glob("*.pdf")))
CPF = gerar_cpf(random.Random(SEED))
CNPJ = gerar_cnpj(random.Random(SEED))

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


@pytest.mark.parametrize(("text", "expected"), ADDRESS_CASES)
def test_regex_endereco_com_flags_presidio(text: str, expected: str | None) -> None:
    pattern = re.compile(_ENDERECO.pattern, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    matches = [] if expected is None else [expected]
    assert [m.group() for m in pattern.finditer(text)] == matches
    assert [m.group() for m in _ENDERECO.finditer(text)] == matches


@pytest.mark.parametrize(("text", "expected"), ADDRESS_CASES)
@pytest.mark.parametrize("lowercase", [False, True])
def test_regex_spans_enderecos(text: str, expected: str | None, lowercase: bool) -> None:
    if lowercase:
        text = text.lower()
        expected = expected.lower() if expected is not None else None
    text = "Documento sintetico\n\n" + text
    entities = RegexDetector().detect(text)
    addresses = [e for e in entities if e.tipo == "ENDERECO"]
    if expected is None:
        assert addresses == []
    else:
        start = text.index(expected)
        assert addresses == [Entity("ENDERECO", expected, start, start + len(expected))]
    assert all("cep" not in e.texto.casefold() and "30130-170" not in e.texto for e in addresses)
    if "30130-170" in text:
        start = text.index("30130-170")
        assert Entity("CEP", "30130-170", start, start + 9) in entities


@pytest.mark.parametrize("caminho", DOCUMENTOS, ids=lambda p: p.stem)
def test_detecta_identificadores_do_corpus(caminho: Path) -> None:
    texto = PdfExtractor().extract(caminho.read_bytes())
    gabarito = json.loads(caminho.with_suffix(".json").read_text(encoding="utf-8"))
    esperados = [
        (e["tipo"], e["texto"])
        for e in gabarito["entidades"]
        if e["tipo"] != "PESSOA"
        and e["texto"] not in gabarito["cpfs_invalidos"]
    ]
    entidades = RegexDetector().detect(texto)
    assert [(e.tipo, e.texto) for e in entidades] == esperados
    assert all(texto[e.start:e.end] == e.texto for e in entidades)


@pytest.mark.parametrize(("tipo", "valor"), [
    ("CPF", CPF),
    ("CPF", re.sub(r"\D", "", CPF)),
    ("CNPJ", CNPJ),
    ("CNPJ", re.sub(r"\D", "", CNPJ)),
    ("EMAIL", "ana.teste+corpus@example.org"),
    ("TELEFONE", "(00) 90000-0001"),
    ("TELEFONE", "(62) 3000-0001"),
    ("TELEFONE", "62 90000-0001"),
    ("TELEFONE", "6230000001"),
    ("TELEFONE", "62900000001"),
    ("TELEFONE", "+55 (62) 90000-0001"),
    ("TELEFONE", "+5562900000001"),
    ("CEP", "00000-001"),
    ("CEP", "00000001"),
])
def test_formatos_e_posicoes(tipo: str, valor: str) -> None:
    texto = f"Inicio: {valor}; fim."
    entidades = RegexDetector().detect(texto)
    assert [(e.tipo, e.texto, e.start, e.end) for e in entidades] == [
        (tipo, valor, 8, 8 + len(valor)),
    ]


@pytest.mark.parametrize("valor", [
    CPF, re.sub(r"\D", "", CPF),
])
def test_cpf_valido(valor: str) -> None:
    assert is_valid_cpf(valor)


@pytest.mark.parametrize("valor", [
    invalidar_cpf(CPF), re.sub(r"\D", "", invalidar_cpf(CPF)),
    CPF[:-2] + str((int(CPF[-2]) + 1) % 10) + CPF[-1],
    "000.000.000-00", "11111111111", "99999999999",
    "", "123", "abc", "123.456.789-0x", "a" + CPF,
    "１２３４５６７８９０１",
])
def test_rejeita_cpf_invalido(valor: str) -> None:
    assert not is_valid_cpf(valor)
    assert not any(e.tipo == "CPF" for e in RegexDetector().detect(valor))


@pytest.mark.parametrize("valor", [
    CNPJ, re.sub(r"\D", "", CNPJ),
])
def test_cnpj_valido(valor: str) -> None:
    assert is_valid_cnpj(valor)


@pytest.mark.parametrize("valor", [
    CNPJ[:-1] + str((int(CNPJ[-1]) + 1) % 10),
    CNPJ[:-2] + str((int(CNPJ[-2]) + 1) % 10) + CNPJ[-1],
    "00.000.000/0000-00", "11111111111111",
    "", "123", "abc", "a" + CNPJ, "１２３４５６７８９０１２３４",
])
def test_rejeita_cnpj_invalido(valor: str) -> None:
    assert not is_valid_cnpj(valor)
    assert not any(e.tipo == "CNPJ" for e in RegexDetector().detect(valor))


def test_repeticoes_unicode_e_ordem() -> None:
    texto = f"Atenção: {CPF}; contato@example.org; novamente {CPF}."
    entidades = RegexDetector().detect(texto)
    assert [e.tipo for e in entidades] == ["CPF", "EMAIL", "CPF"]
    assert all(texto[e.start:e.end] == e.texto for e in entidades)
    assert entidades[0].start == texto.index(CPF)
    assert entidades[-1].start == texto.rindex(CPF)


def test_nao_detecta_subsequencias_de_numeros_ou_palavras() -> None:
    cpf = re.sub(r"\D", "", CPF)
    cnpj = re.sub(r"\D", "", CNPJ)
    assert RegexDetector().detect(
        f"a{cpf}b 7{cpf}7 7{cnpj}7 a00000001b sem-email@localhost"
    ) == []


def test_texto_sem_identificadores() -> None:
    assert RegexDetector().detect("Texto sintetico sem identificadores.") == []


def test_preserva_email_mais_longo_que_identificador_interno() -> None:
    cpf = re.sub(r"\D", "", CPF)
    email = f"{cpf}@example.org"
    entidades = RegexDetector().detect(email)
    assert [(e.tipo, e.texto) for e in entidades] == [("CPF", cpf), ("EMAIL", email)]
