import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from models.errors import ApplicationError


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    runs_db_path: Path = Path("runs.sqlite")
    privacy_mode: Literal["local", "remote_allowed"] = "local"
    llm_base_url: str | None = Field(default=None, repr=False)
    llm_model: str | None = None
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    llm_timeout_s: float = Field(default=30.0, gt=0, allow_inf_nan=False)

    @field_validator("llm_base_url", "llm_model", mode="before")
    @classmethod
    def optional_string(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("runs_db_path", mode="before")
    @classmethod
    def validate_path(cls, value: object) -> object:
        if isinstance(value, str):
            if not value.strip():
                raise ValueError("Caminho do banco invalido.")
            return Path(value)
        return value


def get_settings() -> Settings:
    try:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
        return Settings.model_validate({
            "runs_db_path": os.environ.get("RUNS_DB_PATH", "runs.sqlite"),
            "privacy_mode": os.environ.get("PRIVACY_MODE", "local"),
            "llm_base_url": os.environ.get("LLM_BASE_URL"),
            "llm_model": os.environ.get("LLM_MODEL"),
            "llm_api_key": SecretStr(os.environ["LLM_API_KEY"]) if "LLM_API_KEY" in os.environ else None,
            "llm_timeout_s": float(os.environ.get("LLM_TIMEOUT_S", "30")),
        })
    except (OSError, UnicodeError, ValidationError, ValueError):
        raise ApplicationError("configuration_error") from None
