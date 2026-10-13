import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from models.entity import Entity
from models.run import RunRecord
from models.settings import Settings


def test_contrato_entidade_preserva_interface() -> None:
    entity = Entity("PESSOA", "Caio Ventobravo", 3, 18)
    assert TypeAdapter(Entity).validate_json(
        '{"tipo":"PESSOA","texto":"Caio Ventobravo","start":3,"end":18}'
    ) == entity
    assert "Caio Ventobravo" not in repr(entity)


@pytest.mark.parametrize("alteracao", [
    {"tipo": "DESCONHECIDO"}, {"start": -1}, {"end": 0},
    {"end": 4}, {"texto": ""}, {"start": "0"}, {"end": True},
    {"campo_extra": "nao permitido"},
])
def test_rejeita_entidades_invalidas(alteracao: dict[str, object]) -> None:
    dados = {"tipo": "PESSOA", "texto": "Caio Ventobravo", "start": 0, "end": 15}
    dados.update(alteracao)
    with pytest.raises(ValidationError):
        TypeAdapter(Entity).validate_json(json.dumps(dados))


def test_contrato_run_rejeita_conteudo_e_status_inconsistente() -> None:
    dados = {
        "id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "success", "duration_ms": 1, "error_code": None,
    }
    for alteracao in (
        {"filename": "Caio Ventobravo.pdf"},
        {"error_code": "texto original"},
        {"status": "failure", "error_code": None},
        {"duration_ms": -1},
    ):
        with pytest.raises(ValidationError):
            RunRecord.model_validate_json(json.dumps(dados | alteracao))


def test_configuracao_invalida_e_rejeitada() -> None:
    with pytest.raises(ValidationError):
        Settings(privacy_mode="remote")
    with pytest.raises(ValidationError):
        Settings(runs_db_path="")
