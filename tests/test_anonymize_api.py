from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_anonymization_service
from detectors.entity_detector import EntityDetectionError, EntityDetector
from fixtures.gerar_corpus import DESTINO
from services.anonymization_service import AnonymizationService
from services.pdf_extractor import PdfExtractionError
from services.pseudonym_replacer import ReplacementError

pytestmark = pytest.mark.usefixtures("sem_rede")


@pytest.fixture
def client(detector_fixture: EntityDetector) -> Iterator[TestClient]:
    app.dependency_overrides[get_anonymization_service] = lambda: AnonymizationService(detector_fixture)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_anonymization_service, None)


def test_post_anonymize_devolve_apenas_markdown(client: TestClient) -> None:
    response = client.post(
        "/anonymize",
        files={"file": ("contrato.pdf", (DESTINO / "contrato.pdf").read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "[PESSOA_1]" in response.text
    assert "[CPF_1]" in response.text
    assert "[ENDERECO_1]" in response.text
    assert "Caio Ventobravo" not in response.text
    assert response.text.count("[PESSOA_1]") == 2


def test_openapi_documenta_markdown(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    content = schema["paths"]["/anonymize"]["post"]["responses"]["200"]["content"]
    assert set(content) == {"text/markdown"}
    assert content["text/markdown"]["schema"]["type"] == "string"


@pytest.mark.parametrize("pdf", [b"nao e PDF", b"%PDF-1.7\ncorrompido"])
def test_api_pdf_invalido(client: TestClient, pdf: bytes) -> None:
    response = client.post(
        "/anonymize", files={"file": ("arquivo.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_pdf"


def test_api_rejeita_dois_arquivos(client: TestClient) -> None:
    pdf = (DESTINO / "contrato.pdf").read_bytes()
    response = client.post("/anonymize", files=[
        ("file", ("a.pdf", pdf, "application/pdf")),
        ("file", ("b.pdf", pdf, "application/pdf")),
    ])
    assert response.status_code == 422


def test_api_validacao_nao_expoe_entrada(client: TestClient) -> None:
    segredo_sintetico = "VALOR-PRIVADO-SINTETICO"
    response = client.post("/anonymize", data={"file": segredo_sintetico})
    assert response.status_code == 422
    assert segredo_sintetico not in response.text


@pytest.mark.parametrize(("erro", "status", "codigo"), [
    (PdfExtractionError("extraction_failed"), 500, "extraction_failed"),
    (EntityDetectionError("detector_unavailable"), 503, "detector_unavailable"),
    (EntityDetectionError("detection_failed"), 500, "detection_failed"),
    (ReplacementError(), 500, "invalid_entities"),
])
def test_api_falhas_sem_resultado_parcial(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    erro: Exception,
    status: int,
    codigo: str,
) -> None:
    def falhar(self: AnonymizationService, pdf: bytes) -> str:
        raise erro

    monkeypatch.setattr(AnonymizationService, "anonymize", falhar)
    response = client.post(
        "/anonymize", files={"file": ("arquivo.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert response.status_code == status
    assert response.json()["code"] == codigo
    assert response.headers["content-type"].startswith("application/json")


def test_health_nao_carrega_detector(client: TestClient) -> None:
    def nao_chamar() -> AnonymizationService:
        pytest.fail("Health nao deve inicializar o servico.")

    app.dependency_overrides[get_anonymization_service] = nao_chamar
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.presidio
def test_api_com_presidio_real_sem_rede() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/anonymize",
            files={"file": (
                "nota_fiscal_simples.pdf",
                (DESTINO / "nota_fiscal_simples.pdf").read_bytes(),
                "application/pdf",
            )},
        )
    assert response.status_code == 200
    assert response.text.count("[PESSOA_1]") == 2
    assert "Bruno Pedraclara" not in response.text
    assert "Rua das Nuvens de Papel, 50, Vila Inventada" not in response.text
    assert "[CPF_1]" in response.text
