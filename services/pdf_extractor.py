from io import BytesIO
from typing import Literal

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSException
from pdfplumber.page import Page
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException

from models.errors import ApplicationError
from services.privacy_logging import sensitive_processing

ExtractionErrorCode = Literal["invalid_pdf", "protected_pdf", "no_text", "extraction_failed"]


class PdfExtractionError(ApplicationError, ValueError):
    def __init__(self, code: ExtractionErrorCode) -> None:
        super().__init__(code)


def _page_markdown(page: Page) -> str:
    linhas: list[str] = []
    bottom: float | None = None
    height = 0.0
    for linha in page.extract_text_lines(return_chars=False):
        texto = str(linha["text"]).strip()
        if not texto:
            continue
        top = float(linha["top"])
        if bottom is not None and top - bottom > max(height, 3.0):
            linhas.append("")
        linhas.append(texto)
        bottom = float(linha["bottom"])
        height = bottom - top
    return "\n".join(linhas)


class PdfExtractor:
    @sensitive_processing()
    def extract(self, pdf: bytes) -> str:
        if not pdf.startswith(b"%PDF-"):
            raise PdfExtractionError("invalid_pdf")
        paginas: list[str] = []
        try:
            with pdfplumber.open(BytesIO(pdf)) as documento:
                for page in documento.pages:
                    texto = _page_markdown(page)
                    if texto:
                        paginas.append(texto)
                    page.close()
        except (PdfminerException, MalformedPDFException, PSException, ValueError) as error:
            cause = error.args[0] if isinstance(error, PdfminerException) and error.args else error
            if isinstance(cause, PDFEncryptionError):
                raise PdfExtractionError("protected_pdf") from None
            if isinstance(cause, (PDFSyntaxError, MalformedPDFException)):
                raise PdfExtractionError("invalid_pdf") from None
            raise PdfExtractionError("extraction_failed") from None
        if not paginas:
            raise PdfExtractionError("no_text")
        return "\n\n".join(paginas)
