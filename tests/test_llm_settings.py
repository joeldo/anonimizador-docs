from pathlib import Path

import pytest
from pydantic import ValidationError

from models.run import RunRecord
from models.settings import Settings, get_settings


def test_dotenv_llm_nao_sobrescreve_ambiente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dotenv import load_dotenv

    path = tmp_path / ".env"
    path.write_text(
        "LLM_BASE_URL=http://localhost:11434/v1\nLLM_MODEL=modelo-dotenv\n"
        "LLM_API_KEY=chave-sintetica\nLLM_TIMEOUT_S=15\nPRIVACY_MODE=local\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_MODEL", "modelo-ambiente")
    monkeypatch.setattr("models.settings.load_dotenv", lambda *a, **kw: load_dotenv(path, override=False))
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_TIMEOUT_S"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    config = get_settings()
    assert config.llm_base_url == "http://localhost:11434/v1"
    assert config.llm_model == "modelo-ambiente"
    assert config.llm_timeout_s == 15
    assert config.llm_api_key is not None
    assert config.llm_api_key.get_secret_value() == "chave-sintetica"


def test_metadados_detector_rejeitam_valores_livres() -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    values = {
        "id": uuid4(), "created_at": datetime.now(timezone.utc),
        "status": "success", "duration_ms": 0, "error_code": None,
    }
    for changes in (
        {"detector_used": "Caio Ventobravo"}, {"fallback_reason": "conteudo original"},
        {"detector_used": "llm", "fallback_reason": "timeout"},
    ):
        with pytest.raises(ValidationError):
            RunRecord.model_validate(values | changes)
    assert Settings(privacy_mode="remote_allowed").privacy_mode == "remote_allowed"
