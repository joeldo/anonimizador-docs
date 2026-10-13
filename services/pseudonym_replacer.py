import re
from collections.abc import Sequence
from models.entity import ENTITY_TYPES, Entity, EntityType
from models.errors import ApplicationError


class ReplacementError(ApplicationError, ValueError):
    def __init__(self) -> None:
        super().__init__("invalid_entities")


def select_entities(text: str, entities: Sequence[Entity]) -> list[Entity]:
    for entity in entities:
        if (
            entity.tipo not in ENTITY_TYPES
            or not 0 <= entity.start < entity.end <= len(text)
            or text[entity.start:entity.end] != entity.texto
        ):
            raise ReplacementError()
    selecionadas: list[Entity] = []
    for entity in sorted(set(entities), key=lambda e: (-(e.end - e.start), e.start, e.tipo)):
        if not any(entity.start < e.end and e.start < entity.end for e in selecionadas):
            selecionadas.append(entity)
    return sorted(selecionadas, key=lambda e: e.start)


def _entity_key(entity: Entity) -> tuple[EntityType, str]:
    value = entity.texto
    if entity.tipo in ("CPF", "CNPJ", "CEP", "TELEFONE"):
        value = re.sub(r"[^0-9]", "", value)
        if entity.tipo == "TELEFONE" and value.startswith("55") and len(value) in (12, 13):
            value = value[2:]
    elif entity.tipo == "EMAIL":
        local, separator, domain = value.rpartition("@")
        value = local + separator + domain.casefold()
    else:
        value = " ".join(value.split()).casefold()
    return entity.tipo, value


class PseudonymReplacer:
    def replace(self, text: str, entities: Sequence[Entity]) -> str:
        selecionadas = select_entities(text, entities)
        pseudonimos: dict[tuple[EntityType, str], str] = {}
        contadores: dict[EntityType, int] = {}
        partes: list[str] = []
        cursor = 0
        for entity in selecionadas:
            key = _entity_key(entity)
            if key not in pseudonimos:
                numero = contadores.get(entity.tipo, 0) + 1
                while f"[{entity.tipo}_{numero}]" in text:
                    numero += 1
                contadores[entity.tipo] = numero
                pseudonimos[key] = f"[{entity.tipo}_{numero}]"
            partes.extend((text[cursor:entity.start], pseudonimos[key]))
            cursor = entity.end
        partes.append(text[cursor:])
        return "".join(partes)
