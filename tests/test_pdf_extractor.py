import json
import traceback
from io import BytesIO
from pathlib import Path

import pdfplumber
import pytest
from PIL import Image
from pypdf import PdfWriter
from pdfplumber.utils.exceptions import PdfminerException
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from fixtures.gerar_corpus import DESTINO
from services.pdf_extractor import PdfExtractionError, PdfExtractor

pytestmark = pytest.mark.usefixtures("sem_rede")
DOCUMENTOS = tuple(sorted(DESTINO.glob("*.pdf")))


def test_corpus_disponivel() -> None:
    assert len(DOCUMENTOS) == 6


def pdf_de_paginas(paginas: list[list[tuple[int, str]]]) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1)
    for linhas in paginas:
        canvas.setFont("Helvetica", 12)
        for y, texto in linhas:
            canvas.drawString(40, y, texto)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def pdf_com_imagem(misto: bool = False) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1)
    if misto:
        canvas.drawString(40, 780, "Pagina textual sintetica.")
        canvas.showPage()
    canvas.drawImage(ImageReader(Image.new("RGB", (20, 20), "white")), 40, 700)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


@pytest.mark.parametrize("caminho", DOCUMENTOS, ids=lambda p: p.stem)
def test_extrai_corpus(caminho: Path) -> None:
    markdown = PdfExtractor().extract(caminho.read_bytes())
    gabarito = json.loads(caminho.with_suffix(".json").read_text(encoding="utf-8"))
    assert "DOCUMENTO SINTETICO" in markdown
    posicao = 0
    for entidade in gabarito["entidades"]:
        inicio = markdown.find(entidade["texto"], posicao)
        assert inicio >= 0
        posicao = inicio + len(entidade["texto"])


def test_preserva_paginas_e_paragrafos() -> None:
    pdf = pdf_de_paginas([
        [(780, "Primeiro paragrafo."), (762, "Continuacao do paragrafo."),
         (720, "Segundo paragrafo.")],
        [(780, "Texto da segunda pagina.")],
    ])
    assert PdfExtractor().extract(pdf) == (
        "Primeiro paragrafo.\nContinuacao do paragrafo.\n\n"
        "Segundo paragrafo.\n\nTexto da segunda pagina."
    )


@pytest.mark.parametrize("pdf", [
    b"", b"nao e PDF", b"\x89PNG\r\n\x1a\n",
    b"%PDF-1.7\nconteudo corrompido\n%%EOF",
])
def test_rejeita_pdf_invalido(pdf: bytes) -> None:
    with pytest.raises(PdfExtractionError) as erro:
        PdfExtractor().extract(pdf)
    assert erro.value.code == "invalid_pdf"
    assert "conteudo corrompido" not in str(erro.value)


def test_rejeita_pdf_protegido() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt("senha-sintetica", algorithm="RC4-128")
    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(PdfExtractionError) as erro:
        PdfExtractor().extract(buffer.getvalue())
    assert erro.value.code == "protected_pdf"


@pytest.mark.parametrize("pdf", [
    pdf_de_paginas([[]]),
    pdf_de_paginas([[(780, "   ")]]),
    pdf_com_imagem(),
])
def test_rejeita_pdf_sem_texto(pdf: bytes) -> None:
    with pytest.raises(PdfExtractionError) as erro:
        PdfExtractor().extract(pdf)
    assert erro.value.code == "no_text"


def test_pdf_misto_nao_executa_ocr() -> None:
    assert PdfExtractor().extract(pdf_com_imagem(misto=True)) == "Pagina textual sintetica."


def test_preserva_identificadores_e_unicode() -> None:
    pdf = pdf_de_paginas([[(780, "Atenção: contato_teste@example.org.")]])
    assert PdfExtractor().extract(pdf) == "Atenção: contato_teste@example.org."


def test_falha_do_parser_nao_expoe_mensagem_original(monkeypatch: pytest.MonkeyPatch) -> None:
    def falhar(*_args: object, **_kwargs: object) -> None:
        raise PdfminerException(ValueError("DADO-SINTETICO-QUE-NAO-DEVE-VAZAR"))

    monkeypatch.setattr(pdfplumber, "open", falhar)
    with pytest.raises(PdfExtractionError) as erro:
        PdfExtractor().extract(b"%PDF-1.7\n")
    assert erro.value.code == "extraction_failed"
    assert "DADO-SINTETICO-QUE-NAO-DEVE-VAZAR" not in "".join(
        traceback.format_exception(erro.value)
    )
