"""Согласованность опубликованных data/*.json — их пересобирает tools/parse_config.py."""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
pytestmark = pytest.mark.skipif(not (DATA / "config.json").exists(), reason="data/ не собрана")


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ["config", "server"])
def test_summary_matches_sections(name):
    data, summary = load(f"{name}.json"), load(f"{name}_sections.json")
    assert {k: len(v) for k, v in data.items()} == summary


def test_totals_of_v1_3_12():
    # Эталон для v1.3.12. Если парсер осознанно меняет разбор — обновить числа вместе с data/.
    summary = load("config_sections.json")
    assert (len(summary), sum(summary.values())) == (50, 13_511)
    server = load("server_sections.json")                   # действия — награды всех квестов
    assert (len(server), sum(server.values()), server["actions"]) == (21, 11_782, 2_431)


@pytest.mark.parametrize("name", ["config", "server"])
def test_every_entity_is_a_node(name):
    for section, entities in load(f"{name}.json").items():
        assert all(isinstance(e.get("tag"), str) and e["tag"] for e in entities), section


def test_locale_totals_of_v1_3_12():
    # Эталон v1.3.12: строк в RU, в EN и общих ключей (часть строк есть только в одном языке).
    ru, en = load("locale_ru.json"), load("locale_en.json")
    assert (len(ru), len(en), len(ru.keys() & en.keys())) == (6_416, 6_305, 6_268)
