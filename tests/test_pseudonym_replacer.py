from concurrent.futures import ThreadPoolExecutor

import pytest

from models.entity import Entity, EntityType
from services.pseudonym_replacer import PseudonymReplacer, ReplacementError

pytestmark = pytest.mark.usefixtures("sem_rede")


def entidade(texto: str, valor: str, tipo: EntityType) -> Entity:
    inicio = texto.index(valor)
    return Entity(tipo, valor, inicio, inicio + len(valor))


@pytest.mark.parametrize("tipo", [
    "PESSOA", "CPF", "CNPJ", "EMAIL", "TELEFONE", "CEP", "ENDERECO",
])
def test_marcadores(tipo: EntityType) -> None:
    valor = "Valor sintetico"
    assert PseudonymReplacer().replace(
        valor, [Entity(tipo, valor, 0, len(valor))],
    ) == f"[{tipo}_1]"


def test_consistencia_numero_por_categoria_e_ordem() -> None:
    texto = "Caio Ventobravo; Ana Florival; Caio Ventobravo; contato@example.org"
    inicio = texto.rindex("Caio Ventobravo")
    entidades = [
        entidade(texto, "Ana Florival", "PESSOA"),
        entidade(texto, "contato@example.org", "EMAIL"),
        entidade(texto, "Caio Ventobravo", "PESSOA"),
        Entity("PESSOA", "Caio Ventobravo", inicio, inicio + 15),
    ]
    assert PseudonymReplacer().replace(texto, entidades) == (
        "[PESSOA_1]; [PESSOA_2]; [PESSOA_1]; [EMAIL_1]"
    )


def test_normalizacao_sem_alterar_offsets() -> None:
    texto = "000.000.001-91; 00000000191; Caio Ventobravo; CAIO  VENTOBRAVO"
    entidades = [
        entidade(texto, "000.000.001-91", "CPF"),
        entidade(texto, "00000000191", "CPF"),
        entidade(texto, "Caio Ventobravo", "PESSOA"),
        entidade(texto, "CAIO  VENTOBRAVO", "PESSOA"),
    ]
    assert PseudonymReplacer().replace(texto, entidades) == (
        "[CPF_1]; [CPF_1]; [PESSOA_1]; [PESSOA_1]"
    )


@pytest.mark.parametrize(("tipo", "primeiro", "segundo"), [
    ("CNPJ", "00.000.000/0001-91", "00000000000191"),
    ("CEP", "00000-001", "00000001"),
    ("TELEFONE", "+55 (00) 90000-0001", "00900000001"),
    ("EMAIL", "contato@EXAMPLE.ORG", "contato@example.org"),
    ("ENDERECO", "Rua Aurora, 10", "RUA  AURORA, 10"),
])
def test_consistencia_de_variantes(tipo: EntityType, primeiro: str, segundo: str) -> None:
    texto = f"{primeiro}; {segundo}"
    entidades = [entidade(texto, primeiro, tipo), entidade(texto, segundo, tipo)]
    assert PseudonymReplacer().replace(texto, entidades) == f"[{tipo}_1]; [{tipo}_1]"


def test_sobreposicao_prefere_maior_e_remove_duplicatas() -> None:
    texto = "Rua Aurora, 10; outro texto"
    longa = entidade(texto, "Rua Aurora, 10", "ENDERECO")
    curta = entidade(texto, "Aurora", "PESSOA")
    replacer = PseudonymReplacer()
    assert replacer.replace(texto, [curta, longa, longa]) == "[ENDERECO_1]; outro texto"
    assert replacer.replace(texto, [longa, curta]) == "[ENDERECO_1]; outro texto"


def test_sobreposicao_parcial_e_empate_deterministico() -> None:
    texto = "abcdefghij"
    menor = Entity("PESSOA", texto[:5], 0, 5)
    maior = Entity("ENDERECO", texto[3:10], 3, 10)
    assert PseudonymReplacer().replace(texto, [menor, maior]) == "abc[ENDERECO_1]"
    empatadas = [
        Entity("PESSOA", texto[:5], 0, 5),
        Entity("ENDERECO", texto[:5], 0, 5),
    ]
    replacer = PseudonymReplacer()
    assert replacer.replace(texto, empatadas) == replacer.replace(texto, empatadas[::-1])


def test_entidades_adjacentes() -> None:
    assert PseudonymReplacer().replace(
        "abcd", [Entity("PESSOA", "ab", 0, 2), Entity("CEP", "cd", 2, 4)],
    ) == "[PESSOA_1][CEP_1]"


@pytest.mark.parametrize("entidade_invalida", [
    Entity("PESSOA", "abcd", 0, 4),
    Entity("PESSOA", "xyz", 0, 3),
])
def test_rejeita_entidade_incompativel(entidade_invalida: Entity) -> None:
    with pytest.raises(ReplacementError, match="Entidades invalidas"):
        PseudonymReplacer().replace("abc", [entidade_invalida])


def test_nao_confunde_marcador_preexistente() -> None:
    texto = "[PESSOA_1] Caio Ventobravo"
    assert PseudonymReplacer().replace(
        texto, [entidade(texto, "Caio Ventobravo", "PESSOA")],
    ) == "[PESSOA_1] [PESSOA_2]"


def test_nao_compartilha_mapeamentos_entre_documentos() -> None:
    replacer = PseudonymReplacer()

    def substituir(nome: str) -> str:
        return replacer.replace(nome, [Entity("PESSOA", nome, 0, len(nome))])

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(substituir, ["Caio Ventobravo", "Ana Florival"])) == [
            "[PESSOA_1]", "[PESSOA_1]",
        ]
