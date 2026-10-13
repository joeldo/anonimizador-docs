import json
import random
from pathlib import Path
from typing import TypedDict

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

SEED = 20261013
DESTINO = Path(__file__).resolve().parent / "corpus"


class Entidade(TypedDict):
    tipo: str
    texto: str


def digito_verificador(digitos: str, pesos: tuple[int, ...]) -> str:
    resto = sum(int(d) * p for d, p in zip(digitos, pesos, strict=True)) % 11
    return str(0 if resto < 2 else 11 - resto)


def gerar_cpf(rng: random.Random) -> str:
    base = "".join(str(rng.randrange(10)) for _ in range(9))
    while len(set(base)) == 1:
        base = "".join(str(rng.randrange(10)) for _ in range(9))
    base += digito_verificador(base, tuple(range(10, 1, -1)))
    base += digito_verificador(base, tuple(range(11, 1, -1)))
    return f"{base[:3]}.{base[3:6]}.{base[6:9]}-{base[9:]}"


def gerar_cnpj(rng: random.Random) -> str:
    base = "".join(str(rng.randrange(10)) for _ in range(8)) + "0001"
    base += digito_verificador(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    base += digito_verificador(base, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return f"{base[:2]}.{base[2:5]}.{base[5:8]}/{base[8:12]}-{base[12:]}"


def invalidar_cpf(cpf: str) -> str:
    return cpf[:-1] + str((int(cpf[-1]) + 1) % 10)


def gravar_pdf(caminho: Path, linhas: list[str]) -> None:
    canvas = Canvas(str(caminho), pagesize=A4, invariant=1, pageCompression=0)
    canvas.setTitle(caminho.stem)
    canvas.setAuthor("Corpus sintetico de testes")
    texto = canvas.beginText(40, A4[1] - 40)
    texto.setFont("Helvetica", 11)
    texto.setLeading(18)
    for linha in linhas:
        texto.textLine(linha)
    canvas.drawText(texto)
    canvas.showPage()
    canvas.save()


def gerar_corpus(destino: Path = DESTINO) -> list[Path]:
    rng = random.Random(SEED)
    destino.mkdir(parents=True, exist_ok=True)
    documentos = (
        ("contrato", "CONTRATO DE PRESTACAO DE SERVICOS", "Caio Ventobravo",
         "Contratante", "Objeto: servicos ficticios para teste de pseudonimizacao."),
        ("oficio", "OFICIO 001/2026", "Helena Florival",
         "Destinataria", "Solicitamos a confirmacao dos dados sinteticos abaixo."),
        ("curriculo", "CURRICULO PROFISSIONAL", "Rafael Nuvemalta",
         "Candidato", "Experiencia: analista de testes em empresa ficticia."),
        ("ata", "ATA DE REUNIAO", "Marina Campolume",
         "Participante", "Pauta: aprovacao de um projeto exclusivamente ficticio."),
        ("nota_fiscal_simples", "NOTA FISCAL SIMPLES - SEM VALOR FISCAL",
         "Bruno Pedraclara", "Cliente", "Item: servico ficticio. Total: R$ 100,00."),
        ("email_impresso", "E-MAIL IMPRESSO", "Luiza Riosereno",
         "Remetente", "Assunto: confirmacao de cadastro ficticio para testes."),
    )
    arquivos: list[Path] = []
    for indice, (nome, titulo, pessoa, papel, descricao) in enumerate(documentos, 1):
        entidades: list[Entidade] = []
        linhas = [titulo, "DOCUMENTO SINTETICO - NAO UTILIZAR EM OPERACOES REAIS", "", descricao, ""]

        def adicionar(rotulo: str, tipo: str, valor: str) -> None:
            linhas.append(f"{rotulo}: {valor}")
            entidades.append({"tipo": tipo, "texto": valor})

        adicionar(papel, "PESSOA", pessoa)
        adicionar("CPF", "CPF", gerar_cpf(rng))
        adicionar("CNPJ da empresa ficticia", "CNPJ", gerar_cnpj(rng))
        adicionar("E-mail", "EMAIL", f"contato{indice}@example.org")
        adicionar("Telefone ficticio", "TELEFONE", f"(00) 90000-000{indice}")
        adicionar("CEP de teste", "CEP", f"00000-00{indice}")
        adicionar("Endereco", "ENDERECO", f"Rua das Nuvens de Papel, {indice * 10}, Vila Inventada")
        cpfs_invalidos: list[str] = []
        if nome in ("contrato", "nota_fiscal_simples"):
            cpf_invalido = invalidar_cpf(gerar_cpf(rng))
            cpfs_invalidos.append(cpf_invalido)
            adicionar("CPF com digito incorreto para teste", "CPF", cpf_invalido)
        linhas.append("")
        adicionar("Responsavel pelo documento ficticio", "PESSOA", pessoa)
        pdf = destino / f"{nome}.pdf"
        gabarito = destino / f"{nome}.json"
        gravar_pdf(pdf, linhas)
        gabarito.write_text(
            json.dumps(
                {
                    "documento": pdf.name,
                    "seed": SEED,
                    "sintetico": True,
                    "entidades": entidades,
                    "cpfs_invalidos": cpfs_invalidos,
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        arquivos.extend((pdf, gabarito))
    return arquivos


if __name__ == "__main__":
    for arquivo in gerar_corpus():
        print(arquivo)
