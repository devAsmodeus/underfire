"""Парсер config.xml на синтетических данных: файлы игры в тестах не нужны."""
import json

import parse_config
import pytest

NS = 'xmlns:inferno="http://rocketjump.ru/inferno"'

# Та же форма, что у настоящего config.xml: документы подряд без общего корня, у каждого своё
# объявление <?xml?> и namespace; секции повторяются, бывают пустые, между сущностями — комментарии.
CONFIG = f"""<?xml version="1.0"?><inferno:units client="1" {NS}>
<unit type="scout" speed="3"><visual src="units/scout"><name>scout::name</name></visual></unit>
<!-- комментарий между сущностями -->
<unit type="tank"/>
</inferno:units>
<?xml version="1.0"?><inferno:stars client="1" {NS}/>
<?xml version="1.0"?><inferno:units client="1" {NS}>
<unit type="walker"><stats><hp>5</hp><hp>6</hp></stats></unit>
</inferno:units>
<?xml version="1.0"?><inferno:quests client="1" {NS}><quest id="q1">Текст</quest></inferno:quests>
"""

# Локаль — тоже склейка документов-секций; ключ может повторяться (побеждает последний).
LOCALE = f"""<?xml version="1.0"?><inferno:abilities {NS}>
<damage><value_1><![CDATA[<font color="#fff66f">@ урона</font>]]></value_1></damage>
<time><value_1><![CDATA[@ секунду]]></value_1><value_2><![CDATA[@ секунды]]></value_2></time>
</inferno:abilities>
<?xml version="1.0"?><inferno:gui {NS}>
<window><title><![CDATA[Старое]]></title><title><![CDATA[Новое]]></title></window>
</inferno:gui>
"""


@pytest.fixture
def out(tmp_path, monkeypatch):
    src, out = tmp_path / "config", tmp_path / "data"
    (src / "locales").mkdir(parents=True)
    out.mkdir()
    (src / "config.xml").write_text(CONFIG, encoding="utf-8")
    (src / "locales" / "ru_locale.xml").write_text(LOCALE, encoding="utf-8")
    monkeypatch.setattr(parse_config, "SRC", src)
    monkeypatch.setattr(parse_config, "OUT", out)
    return out


def test_sections_merge_across_documents(out):
    sections, summary = parse_config.parse_config()
    assert [e["attr"]["type"] for e in sections["units"]] == ["scout", "tank", "walker"]
    assert summary == {"units": 3, "quests": 1}


def test_empty_sections_are_skipped(out):
    sections, _ = parse_config.parse_config()
    assert "stars" not in sections


def test_node_is_lossless(out):
    sections, _ = parse_config.parse_config()
    scout, tank, walker = sections["units"]
    assert scout == {
        "tag": "unit",
        "attr": {"type": "scout", "speed": "3"},
        "children": [{"tag": "visual", "attr": {"src": "units/scout"},
                      "children": [{"tag": "name", "text": "scout::name"}]}],
    }
    assert tank == {"tag": "unit", "attr": {"type": "tank"}}
    hp = walker["children"][0]["children"]          # повторы тегов сохраняются по порядку
    assert hp == [{"tag": "hp", "text": "5"}, {"tag": "hp", "text": "6"}]
    assert sections["quests"] == [{"tag": "quest", "attr": {"id": "q1"}, "text": "Текст"}]


def test_outputs_written(out):
    parse_config.parse_config()
    assert json.loads((out / "config_sections.json").read_text()) == {"units": 3, "quests": 1}
    assert set(json.loads((out / "config.json").read_text())) == {"units", "quests"}


def test_locale_reads_every_document(out):
    assert parse_config.parse_locale("ru") == 4
    assert json.loads((out / "locale_ru.json").read_text()) == {
        "abilities/damage/value_1": '<font color="#fff66f">@ урона</font>',
        "abilities/time/value_1": "@ секунду",
        "abilities/time/value_2": "@ секунды",
        "gui/window/title": "Новое",
    }


def test_missing_locale_is_skipped(out):
    assert parse_config.parse_locale("en") == 0
    assert not (out / "locale_en.json").exists()
