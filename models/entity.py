from dataclasses import field
from typing import Annotated, Literal, get_args

from pydantic import ConfigDict, Field
from pydantic.dataclasses import dataclass

EntityType = Literal["PESSOA", "CPF", "CNPJ", "EMAIL", "TELEFONE", "CEP", "ENDERECO"]
ENTITY_TYPES: tuple[EntityType, ...] = get_args(EntityType)


@dataclass(
    frozen=True,
    config=ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True),
)
class Entity:
    tipo: EntityType
    texto: Annotated[str, Field(min_length=1)] = field(repr=False)
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]

    def __post_init__(self) -> None:
        if self.end <= self.start or self.end - self.start != len(self.texto):
            raise ValueError("Intervalo de entidade invalido.")
