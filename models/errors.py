from typing import Literal

from pydantic import BaseModel, ConfigDict

ErrorCode = Literal[
    "invalid_pdf", "protected_pdf", "no_text", "extraction_failed",
    "detector_unavailable", "detection_failed", "invalid_entities", "invalid_request",
    "database_unavailable", "configuration_error", "invalid_corpus", "read_failed",
    "not_found", "method_not_allowed",
]

ERRORS: dict[ErrorCode, tuple[int, str]] = {
    "invalid_pdf": (422, "Arquivo PDF invalido."),
    "protected_pdf": (422, "PDF protegido sem possibilidade de leitura."),
    "no_text": (422, "PDF sem texto extraivel."),
    "extraction_failed": (500, "Falha ao extrair texto do PDF."),
    "detector_unavailable": (503, "Detector local indisponivel. Instale pt_core_news_lg."),
    "detection_failed": (500, "Falha na deteccao de entidades."),
    "invalid_entities": (500, "Entidades invalidas para substituicao."),
    "invalid_request": (422, "Requisicao invalida."),
    "database_unavailable": (503, "Repositorio de metadados indisponivel."),
    "configuration_error": (503, "Configuracao invalida."),
    "invalid_corpus": (422, "Corpus ou gabarito invalido."),
    "read_failed": (422, "Nao foi possivel ler o arquivo PDF."),
    "not_found": (404, "Recurso nao encontrado."),
    "method_not_allowed": (405, "Metodo nao permitido."),
}


class ApplicationError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        self.status_code, self.message = ERRORS[code]
        super().__init__(self.message)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorCode
    message: str
