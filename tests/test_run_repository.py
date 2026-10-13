import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from detectors.entity_detector import EntityDetector
from fixtures.gerar_corpus import DESTINO
from models.errors import ApplicationError
from models.run import RunRecord
from repositories.run_repository import RunRepository
from services.anonymization_service import AnonymizationService
from services.pdf_extractor import PdfExtractionError

pytestmark = pytest.mark.usefixtures("sem_rede")


def registro() -> RunRecord:
    return RunRecord(
        id=uuid4(), created_at=datetime.now(timezone.utc),
        status="success", duration_ms=1, error_code=None,
    )


def test_sqlite_contem_somente_metadados(
    tmp_path: Path, detector_fixture: EntityDetector,
) -> None:
    path = tmp_path / "runs.sqlite"
    repo = RunRepository(path)
    service = AnonymizationService(detector_fixture, repository=repo)
    service.anonymize((DESTINO / "contrato.pdf").read_bytes())
    with pytest.raises(PdfExtractionError):
        service.anonymize(b"nao e PDF")
    page = repo.list_runs()
    assert page.total == 2
    assert {run.status for run in page.items} == {"success", "failure"}
    failed = next(run for run in page.items if run.status == "failure")
    assert failed.error_code == "invalid_pdf"
    with closing(sqlite3.connect(path)) as conn:
        tabelas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        assert tabelas == [("runs",)]
        colunas = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
        assert colunas == {
            "id", "created_at", "status", "duration_ms", "error_code", "detector_used", "fallback_reason",
        }
        conteudo = repr(conn.execute("SELECT * FROM runs").fetchall())
        assert "Caio Ventobravo" not in conteudo
        assert "contrato.pdf" not in conteudo
        assert "[PESSOA_1]" not in conteudo


def test_repositorio_persistente_paginado_e_concorrente(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    repo = RunRepository(path)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(repo.add, [registro() for _ in range(8)]))
    page = RunRepository(path).list_runs(limit=3, offset=2)
    assert (page.total, page.limit, page.offset, len(page.items)) == (8, 3, 2, 3)
    assert len({r.id for r in RunRepository(path).list_runs().items}) == 8
    assert [r.created_at for r in page.items] == sorted(
        [r.created_at for r in page.items], reverse=True,
    )


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (101, 0), (10, -1), (10, 2**63)])
def test_repositorio_rejeita_paginacao_invalida(tmp_path: Path, limit: int, offset: int) -> None:
    with pytest.raises(ApplicationError) as erro:
        RunRepository(tmp_path / "runs.sqlite").list_runs(limit=limit, offset=offset)
    assert erro.value.code == "invalid_request"


def test_falha_sqlite_e_explicita_e_nao_expoe_caminho(tmp_path: Path) -> None:
    with pytest.raises(ApplicationError) as erro:
        RunRepository(tmp_path / "diretorio-inexistente" / "privado.sqlite")
    assert erro.value.code == "database_unavailable"
    assert "privado" not in str(erro.value)


def test_falha_persistencia_nao_entrega_sucesso(
    tmp_path: Path, detector_fixture: EntityDetector, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = RunRepository(tmp_path / "runs.sqlite")

    def falhar(run: RunRecord) -> None:
        raise ApplicationError("database_unavailable")

    monkeypatch.setattr(repo, "add", falhar)
    with pytest.raises(ApplicationError):
        AnonymizationService(detector_fixture, repository=repo).anonymize(
            (DESTINO / "contrato.pdf").read_bytes()
        )


def test_migracao_release_2_preserva_registros_e_e_idempotente(tmp_path: Path) -> None:
    path = tmp_path / "antigo.sqlite"
    run = registro()
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE runs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL, "
            "duration_ms INTEGER NOT NULL, error_code TEXT)"
        )
        conn.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)", (
            str(run.id), run.created_at.isoformat(), run.status, run.duration_ms, run.error_code,
        ))
    with ThreadPoolExecutor(max_workers=2) as executor:
        repos = list(executor.map(RunRepository, [path, path]))
    for repo in repos:
        assert repo.list_runs().items == [run]
    RunRepository(path).add(registro())
    assert RunRepository(path).list_runs().total == 2


@pytest.mark.parametrize(("column", "value"), [
    ("detector_used", "Caio Ventobravo"), ("fallback_reason", "texto-original"),
    ("fallback_reason", "timeout"),
])
def test_sqlite_rejeita_relatorio_livre_ou_inconsistente(
    tmp_path: Path, column: str, value: str,
) -> None:
    path = tmp_path / "restrito.sqlite"
    repo = RunRepository(path)
    repo.add(registro())
    with closing(sqlite3.connect(path)) as conn, conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(f"UPDATE runs SET {column} = ?", (value,))
