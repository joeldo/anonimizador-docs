import json
import os
import re
import socket
from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path

import pytest

from detectors.entity_detector import EntityDetector
from models.entity import Entity, EntityType
from fixtures.gerar_corpus import DESTINO


@pytest.fixture(autouse=True)
def isolar_banco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from api.main import get_anonymization_service, get_run_repository

    monkeypatch.setenv("RUNS_DB_PATH", str(tmp_path / "runs.sqlite"))
    monkeypatch.setenv("PRIVACY_MODE", "local")
    for key in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_TIMEOUT_S"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("models.settings.load_dotenv", lambda *args, **kwargs: False)
    get_anonymization_service.cache_clear()
    get_run_repository.cache_clear()
    try:
        yield
    finally:
        get_anonymization_service.cache_clear()
        get_run_repository.cache_clear()


@pytest.fixture
def sem_rede(monkeypatch: pytest.MonkeyPatch) -> None:
    criando_par = ContextVar("criando_par", default=False)
    socketpair = socket.socketpair
    connect = socket.socket.connect

    def bloquear(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Este teste nao permite acesso a rede.")

    def conectar(sock: socket.socket, address: tuple[str, int]) -> None:
        if criando_par.get() and address[0] in ("127.0.0.1", "::1"):
            connect(sock, address)
        else:
            bloquear()

    def criar_par(*args: int, **kwargs: int) -> tuple[socket.socket, socket.socket]:
        # No Windows, asyncio usa uma conexao loopback interna para socketpair.
        token = criando_par.set(True)
        try:
            return socketpair(*args, **kwargs)
        finally:
            criando_par.reset(token)

    monkeypatch.setattr(socket, "socketpair", criar_par)
    monkeypatch.setattr(socket.socket, "connect", conectar)
    monkeypatch.setattr(socket.socket, "connect_ex", bloquear)
    monkeypatch.setattr(socket, "getaddrinfo", bloquear)


@pytest.fixture
def subprocess_offline_env(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "sitecustomize.py").write_text(
        "import socket\n"
        "def bloquear(*args, **kwargs):\n"
        "    raise RuntimeError('Rede bloqueada no teste.')\n"
        "socket.socket.connect = bloquear\n"
        "socket.socket.connect_ex = bloquear\n"
        "socket.getaddrinfo = bloquear\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    env.update(LLM_BASE_URL="", LLM_MODEL="", LLM_API_KEY="", LLM_TIMEOUT_S="30", PRIVACY_MODE="local")
    return env


@pytest.fixture
def detector_fixture() -> EntityDetector:
    esperadas: set[tuple[EntityType, str]] = set()
    for caminho in DESTINO.glob("*.json"):
        gabarito = json.loads(caminho.read_text(encoding="utf-8"))
        for entidade in gabarito["entidades"]:
            if entidade["tipo"] in ("PESSOA", "ENDERECO"):
                tipo: EntityType = "PESSOA" if entidade["tipo"] == "PESSOA" else "ENDERECO"
                esperadas.add((tipo, entidade["texto"]))

    class FixtureDetector:
        def detect(self, text: str) -> list[Entity]:
            return [
                Entity(tipo, valor, match.start(), match.end())
                for tipo, valor in sorted(esperadas)
                for match in re.finditer(re.escape(valor), text)
            ]

    return FixtureDetector()
