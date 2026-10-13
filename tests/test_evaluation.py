from pathlib import Path
import subprocess
import sys

import pytest

from detectors.entity_detector import EntityDetector
from fixtures.gerar_corpus import DESTINO
from models.entity import ENTITY_TYPES, Entity
from models.errors import ApplicationError
from scripts import avaliar
from scripts.avaliar import evaluate_corpus, score_entities

pytestmark = pytest.mark.usefixtures("sem_rede")


def test_precisao_recall_dois_tercos() -> None:
    expected = [Entity("PESSOA", "abc", i, i + 3) for i in (0, 10, 20)]
    predicted = [Entity("PESSOA", "abc", i, i + 3) for i in (0, 10, 30)]
    metrics = next(m for m in score_entities(expected, predicted) if m.tipo == "PESSOA")
    assert (metrics.tp, metrics.fp, metrics.fn) == (2, 1, 1)
    assert metrics.precisao == pytest.approx(2 / 3, abs=1e-12)
    assert metrics.recall == pytest.approx(2 / 3, abs=1e-12)


def test_intervalo_exato_e_ocorrencias_repetidas() -> None:
    expected = [Entity("PESSOA", "abc", 0, 3), Entity("PESSOA", "abc", 10, 13)]
    predicted = [Entity("PESSOA", "abc", 0, 3), Entity("PESSOA", "abc", 11, 14)]
    metrics = next(m for m in score_entities(expected, predicted) if m.tipo == "PESSOA")
    assert (metrics.tp, metrics.fp, metrics.fn) == (1, 1, 1)


def test_denominadores_zero_nao_sao_confundidos_com_zero() -> None:
    empty = score_entities([], [])
    assert {m.tipo for m in empty} == set(ENTITY_TYPES)
    assert all(m.precisao is None and m.recall is None for m in empty)
    entidade = Entity("CPF", "abc", 0, 3)
    fp = next(m for m in score_entities([], [entidade]) if m.tipo == "CPF")
    fn = next(m for m in score_entities([entidade], []) if m.tipo == "CPF")
    assert (fp.precisao, fp.recall) == (0.0, None)
    assert (fn.precisao, fn.recall) == (None, 0.0)


def test_avaliacao_corpus_com_oraculo_e_regex(detector_fixture: EntityDetector) -> None:
    report = evaluate_corpus(DESTINO, detector_fixture)
    assert report.documentos == 6
    assert report.cpfs_invalidos_excluidos == 2
    assert {m.tipo for m in report.metricas} == set(ENTITY_TYPES)
    for metrics in report.metricas:
        assert (metrics.fp, metrics.fn) == (0, 0)
        assert metrics.precisao == 1.0
        assert metrics.recall == 1.0
        assert metrics.tp == (12 if metrics.tipo == "PESSOA" else 6)


def test_corpus_vazio_e_erro_explicito(tmp_path: Path, detector_fixture: EntityDetector) -> None:
    with pytest.raises(ApplicationError) as erro:
        evaluate_corpus(tmp_path, detector_fixture)
    assert erro.value.code == "invalid_corpus"


def test_main_erro_nao_imprime_resultado_parcial(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert avaliar.main(["--corpus", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "invalid_corpus: Corpus ou gabarito invalido.\n"


@pytest.mark.presidio
def test_avaliador_subprocesso_sem_rede_e_sem_persistir_documentos(
    subprocess_offline_env: dict[str, str],
) -> None:
    script = Path(avaliar.__file__)
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True,
        env=subprocess_offline_env, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "PDFs: 6 | CPFs invalidos excluidos: 2" in result.stdout
    rows = [row.split() for row in result.stdout.splitlines()[2:]]
    assert {row[0] for row in rows} == set(ENTITY_TYPES)
    assert all(len(row) == 6 for row in rows)
    assert not Path(subprocess_offline_env["RUNS_DB_PATH"]).exists()
