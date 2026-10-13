import json
import re
from pathlib import Path

from pypdf import PdfReader

from fixtures.gerar_corpus import gerar_corpus


def cpf_valido(valor: str) -> bool:
    digitos = [int(d) for d in re.sub(r"\D", "", valor)]
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for tamanho in (9, 10):
        calculado = sum(digitos[i] * (tamanho + 1 - i) for i in range(tamanho))
        verificador = (calculado * 10 % 11) % 10
        if digitos[tamanho] != verificador:
            return False
    return True


def cnpj_valido(valor: str) -> bool:
    digitos = [int(d) for d in re.sub(r"\D", "", valor)]
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    for tamanho in (12, 13):
        soma = sum(digitos[i] * ((tamanho - 1 - i) % 8 + 2) for i in range(tamanho))
        resto = soma % 11
        if digitos[tamanho] != (0 if resto < 2 else 11 - resto):
            return False
    return True


def test_corpus_deterministico(tmp_path: Path) -> None:
    arquivos = gerar_corpus(tmp_path)
    assert len(arquivos) == 12
    assert len(list(tmp_path.glob("*.pdf"))) == 6
    assert len(list(tmp_path.glob("*.json"))) == 6
    conteudos = {p.name: p.read_bytes() for p in arquivos}
    repetidos = gerar_corpus(tmp_path)
    assert {p.name: p.read_bytes() for p in repetidos} == conteudos


def test_gabaritos_e_identificadores(tmp_path: Path) -> None:
    gerar_corpus(tmp_path)
    validos = 0
    invalidos = 0
    cnpjs = 0
    for caminho in sorted(tmp_path.glob("*.json")):
        gabarito = json.loads(caminho.read_text(encoding="utf-8"))
        reader = PdfReader(tmp_path / gabarito["documento"])
        assert not reader.is_encrypted
        texto = "\n".join(pagina.extract_text() for pagina in reader.pages)
        assert "DOCUMENTO SINTETICO" in texto
        assert {e["tipo"] for e in gabarito["entidades"]} == {
            "PESSOA", "CPF", "CNPJ", "EMAIL", "TELEFONE", "CEP", "ENDERECO",
        }
        posicao = 0
        for entidade in gabarito["entidades"]:
            valor = entidade["texto"]
            inicio = texto.find(valor, posicao)
            assert inicio >= 0, (caminho.name, entidade)
            posicao = inicio + len(valor)
            if entidade["tipo"] == "CPF":
                if valor in gabarito["cpfs_invalidos"]:
                    assert not cpf_valido(valor)
                    invalidos += 1
                else:
                    assert cpf_valido(valor)
                    validos += 1
            elif entidade["tipo"] == "CNPJ":
                assert cnpj_valido(valor)
                cnpjs += 1
        assert sorted(gabarito["cpfs_invalidos"]) == sorted(
            e["texto"] for e in gabarito["entidades"]
            if e["tipo"] == "CPF" and not cpf_valido(e["texto"])
        )
    assert (validos, invalidos, cnpjs) == (6, 2, 6)
