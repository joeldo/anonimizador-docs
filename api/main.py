from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from models.errors import ApplicationError, ErrorResponse
from models.run import MAX_SQLITE_INTEGER, RunPage
from models.settings import get_settings
from repositories.run_repository import RunRepository
from services.anonymization_service import AnonymizationService, create_anonymization_service

app = FastAPI(title="anonimizador-pdf")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@lru_cache(maxsize=1)
def get_run_repository() -> RunRepository:
    return RunRepository(get_settings().runs_db_path)


@lru_cache(maxsize=1)
def get_anonymization_service() -> AnonymizationService:
    return create_anonymization_service(repository=get_run_repository())


def error_response(error: ApplicationError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=ErrorResponse(code=error.code, message=error.message).model_dump(),
    )


@app.exception_handler(ApplicationError)
def application_error(_request: Request, error: ApplicationError) -> JSONResponse:
    return error_response(error)


@app.exception_handler(RequestValidationError)
def validation_error(_request: Request, _error: RequestValidationError) -> JSONResponse:
    return error_response(ApplicationError("invalid_request"))


@app.exception_handler(HTTPException)
def http_error(_request: Request, error: HTTPException) -> JSONResponse:
    code = "not_found" if error.status_code == 404 else (
        "method_not_allowed" if error.status_code == 405 else "invalid_request"
    )
    response = error_response(ApplicationError(code))
    response.status_code = error.status_code
    if error.headers:
        response.headers.update(error.headers)
    return response


@app.post(
    "/anonymize",
    response_class=Response,
    responses={
        200: {"content": {"text/markdown": {"schema": {"type": "string"}}}},
        422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 503: {"model": ErrorResponse},
    },
)
async def anonymize(
    request: Request,
    file: Annotated[UploadFile, File()],
    service: Annotated[AnonymizationService, Depends(get_anonymization_service)],
) -> Response:
    try:
        form = await request.form()
        if len(form.multi_items()) != 1:
            raise ApplicationError("invalid_request")
        pdf = await file.read()
        markdown = await run_in_threadpool(service.anonymize, pdf)
        return Response(content=markdown, media_type="text/markdown")
    finally:
        await file.close()


@app.get("/runs", response_model=RunPage, responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def runs(
    repository: Annotated[RunRepository, Depends(get_run_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=MAX_SQLITE_INTEGER)] = 0,
) -> RunPage:
    return repository.list_runs(limit=limit, offset=offset)
