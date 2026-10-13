import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from models.errors import ApplicationError
from services.anonymization_service import create_anonymization_service


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pseudonimizar PDF de texto em Markdown.")
    parser.add_argument("pdf", type=Path, help="PDF com camada de texto.")
    args = parser.parse_args(argv)
    try:
        pdf = args.pdf.read_bytes()
    except OSError:
        error = ApplicationError("read_failed")
        sys.stderr.write(f"{error.code}: {error.message}\n")
        return 2
    try:
        markdown = create_anonymization_service().anonymize(pdf)
    except ApplicationError as error:
        sys.stderr.write(f"{error.code}: {error.message}\n")
        return 1
    sys.stdout.write(markdown + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
