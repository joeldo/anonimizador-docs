import re

from models.entity import Entity, EntityType

_CPF = re.compile(r"(?<!\w)(?:[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}|[0-9]{11})(?!\w)")
_CNPJ = re.compile(
    r"(?<!\w)(?:[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}|[0-9]{14})(?!\w)"
)
_EMAIL = re.compile(
    r"(?<![\w.+%-])[A-Za-z0-9._%+-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}(?![\w@-])"
)
_TELEFONE = re.compile(
    r"(?<![\w+])(?:\+55[ ]?)?(?:\([0-9]{2}\)[ ]?|[0-9]{2}[ ]?)"
    r"(?:9[0-9]{4}|[2-9][0-9]{3})[- ]?[0-9]{4}(?!\w)"
)
_CEP = re.compile(r"(?<!\w)[0-9]{5}-?[0-9]{3}(?!\w)")
_ADDRESS_TYPES = (
    r"(?:Rua|R\.|Avenida|Av\.|Travessa|Trav\.|Alameda|Al\.|Pra[cç]a|P[cç]\.|"
    r"Estrada|Estr\.|Rodovia|Rod\.)"
)
_ADDRESS_SEGMENT = r"(?!CEP\b)[^\s,;](?:[^\n,;]*[^\s,;.])?"
_ENDERECO = re.compile(
    rf"\b{_ADDRESS_TYPES}[ \t]+[^\n,;0-9]+?,?[ \t]*\d+[A-Za-z]?"
    rf"(?:(?:[ \t]*,[ \t]*|[ \t]+-[ \t]+){_ADDRESS_SEGMENT})*",
    re.IGNORECASE,
)


def _check_digit(digitos: str, pesos: tuple[int, ...]) -> str:
    resto = sum(int(d) * p for d, p in zip(digitos, pesos, strict=True)) % 11
    return str(0 if resto < 2 else 11 - resto)


def _valid_identifier(
    value: str,
    pattern: re.Pattern[str],
    first_weights: tuple[int, ...],
    second_weights: tuple[int, ...],
) -> bool:
    if pattern.fullmatch(value) is None:
        return False
    digitos = re.sub(r"[^0-9]", "", value)
    if len(set(digitos)) == 1:
        return False
    base = digitos[:-2]
    first = _check_digit(base, first_weights)
    second = _check_digit(base + first, second_weights)
    return digitos[-2:] == first + second


def is_valid_cpf(value: str) -> bool:
    return _valid_identifier(
        value, _CPF, tuple(range(10, 1, -1)), tuple(range(11, 1, -1)),
    )


def is_valid_cnpj(value: str) -> bool:
    return _valid_identifier(
        value, _CNPJ,
        (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
        (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
    )


class RegexDetector:
    def detect(self, text: str) -> list[Entity]:
        entidades: list[Entity] = []
        for tipo, pattern, validator in (
            ("CPF", _CPF, is_valid_cpf),
            ("CNPJ", _CNPJ, is_valid_cnpj),
        ):
            for match in pattern.finditer(text):
                if validator(match.group()):
                    entidades.append(Entity(tipo, match.group(), match.start(), match.end()))
        identificadores = tuple(entidades)
        patterns: tuple[tuple[EntityType, re.Pattern[str]], ...] = (
            ("EMAIL", _EMAIL), ("TELEFONE", _TELEFONE), ("CEP", _CEP), ("ENDERECO", _ENDERECO),
        )
        for tipo, pattern in patterns:
            for match in pattern.finditer(text):
                if tipo == "TELEFONE" and any(
                    e.tipo == "CPF" and e.start == match.start() and e.end == match.end()
                    for e in identificadores
                ):
                    continue
                entidades.append(Entity(tipo, match.group(), match.start(), match.end()))
        return sorted(entidades, key=lambda e: (e.start, e.end, e.tipo))
