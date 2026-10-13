import pytest
from fastapi.testclient import TestClient

from api.main import app, get_anonymization_service, get_run_repository
from detectors.entity_detector import EntityDetector
from fixtures.gerar_corpus import DESTINO
from models.errors import ApplicationError
from repositories.run_repository import RunRepository
from services.anonymization_service import AnonymizationService

pytestmark = pytest.mark.usefixtures("sem_rede")


def test_get_runs_expoe_somente_metadados(detector_fixture: EntityDetector) -> None:
    repo = get_run_repository()
    app.dependency_overrides[get_anonymization_service] = lambda: AnonymizationService(
        detector_fixture, repository=repo,
    )
    try:
        with TestClient(app) as client:
            for pdf in ((DESTINO / "contrato.pdf").read_bytes(), b"nao e PDF"):
                client.post("/anonymize", files={"file": ("privado.pdf", pdf, "application/pdf")})
            response = client.get("/runs", params={"limit": 1, "offset": 0})
            assert response.status_code == 200
            page = response.json()
            assert (page["total"], page["limit"], page["offset"]) == (2, 1, 0)
            assert len(page["items"]) == 1
            assert set(page["items"][0]) == {
                "id", "created_at", "status", "duration_ms", "error_code",
                "detector_used", "fallback_reason",
            }
            assert "Caio Ventobravo" not in response.text
            assert "privado.pdf" not in response.text
            assert client.get("/runs").json()["limit"] == 50
            assert client.get("/runs", params={"limit": 100}).json()["limit"] == 100
            last = client.get("/runs", params={"offset": 2**63 - 1})
            assert last.status_code == 200
            assert last.json()["items"] == []
    finally:
        app.dependency_overrides.pop(get_anonymization_service, None)


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": "TEXTO-PRIVADO"},
    {"offset": 2**63},
])
def test_runs_rejeita_paginacao_sem_expor_entrada(params: dict[str, object]) -> None:
    with TestClient(app) as client:
        response = client.get("/runs", params=params)
    assert response.status_code == 422
    assert set(response.json()) == {"code", "message"}
    assert response.json()["code"] == "invalid_request"
    assert "TEXTO-PRIVADO" not in response.text


def test_runs_falha_de_banco_padronizada(monkeypatch: pytest.MonkeyPatch) -> None:
    def falhar(self: RunRepository, limit: int = 50, offset: int = 0) -> None:
        raise ApplicationError("database_unavailable")

    monkeypatch.setattr(RunRepository, "list_runs", falhar)
    with TestClient(app) as client:
        response = client.get("/runs")
    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"


def test_404_e_405_padronizados() -> None:
    with TestClient(app) as client:
        for method, path, status in (("GET", "/inexistente", 404), ("POST", "/health", 405)):
            response = client.request(method, path)
            assert response.status_code == status
            assert set(response.json()) == {"code", "message"}


@pytest.mark.parametrize(("name", "value"), [("PRIVACY_MODE", "remote"), ("RUNS_DB_PATH", "")])
def test_configuracao_invalida_padronizada(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str,
) -> None:
    monkeypatch.setenv(name, value)
    with TestClient(app) as client:
        response = client.get("/runs")
    assert response.status_code == 503
    assert response.json()["code"] == "configuration_error"
