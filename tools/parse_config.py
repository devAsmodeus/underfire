#!/usr/bin/env python3
"""Сбор под браузер, шаг 1: config.xml (движок Inferno) → структурный JSON + локали.

config.xml — склейка нескольких XML-документов с namespace inferno: и без общего корня.
Разбираем устойчивым парсером lxml(recover), приводим к lossless-дереву и группируем по
верхнеуровневым секциям (buildings, units, soldiers, resources, quests, missions, …).
Локали — такая же склейка документов по секциям (abilities, gui, buildings, …) с CDATA-строками
(@ = подставляемое значение) → плоская карта 'секция/…/ключ' → текст.

    python3 tools/parse_config.py
Вход  : raw/obb_patch/assets/config/{config.xml,locales/*_locale.xml} (patch перекрывает main)
Выход : data/config.json, data/config_sections.json (сводка), data/locale_ru.json, data/locale_en.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "raw/obb_patch/assets/config"          # patch — авторитетная версия
OUT = ROOT / "data"
NS = {"inferno": "http://rocketjump.ru/inferno"}


def _local(tag) -> str:
    if not isinstance(tag, str):
        return "_comment"
    return etree.QName(tag).localname if "}" in tag else tag


def _load_multidoc(path: Path):
    """config.xml — несколько документов подряд: убираем все <?xml?>, оборачиваем в один корень
    с объявленным namespace inferno, парсим с recover."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"<\?xml[^>]*\?>", "", raw)
    wrapped = f'<root xmlns:inferno="{NS["inferno"]}">{raw}</root>'
    p = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    return etree.fromstring(wrapped.encode("utf-8"), p)


def node(el) -> dict:
    """Lossless-узел: тег (без префикса), атрибуты, текст, дети (с сохранением порядка/повторов)."""
    out: dict = {"tag": _local(el.tag)}
    if el.attrib:
        out["attr"] = {_local(k): v for k, v in el.attrib.items()}
    kids = [c for c in el if isinstance(c.tag, str)]
    if kids:
        out["children"] = [node(c) for c in kids]
    else:
        txt = (el.text or "").strip()
        if txt:
            out["text"] = txt
    return out


def parse_config():
    root = _load_multidoc(SRC / "config.xml")
    sections: dict[str, list] = {}                  # секция → список сущностей-узлов
    for sec in root:
        if not isinstance(sec.tag, str):
            continue
        name = _local(sec.tag)
        for ent in sec:
            if isinstance(ent.tag, str):
                sections.setdefault(name, []).append(node(ent))
    (OUT / "config.json").write_text(json.dumps(sections, ensure_ascii=False, indent=1))
    summary = {k: len(v) for k, v in sorted(sections.items(), key=lambda x: -len(x[1]))}
    (OUT / "config_sections.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return sections, summary


def flatten_locale(el, prefix="") -> dict:
    """Вложенные CDATA-строки → плоская карта 'a/b/c' → текст."""
    out = {}
    kids = [c for c in el if isinstance(c.tag, str)]
    if not kids:
        txt = (el.text or "")
        if txt.strip():
            out[prefix] = txt
        return out
    for c in kids:
        key = f"{prefix}/{_local(c.tag)}" if prefix else _local(c.tag)
        out.update(flatten_locale(c, key))
    return out


def parse_locale(lang: str) -> int:
    """Локаль склеена из документов-секций, как config.xml: ключ начинается с имени секции.
    Если ключ повторяется, остаётся последнее значение."""
    path = SRC / f"locales/{lang}_locale.xml"
    if not path.exists():
        return 0
    flat: dict[str, str] = {}
    for sec in _load_multidoc(path):
        if isinstance(sec.tag, str):
            flat.update(flatten_locale(sec, _local(sec.tag)))
    (OUT / f"locale_{lang}.json").write_text(json.dumps(flat, ensure_ascii=False, indent=1))
    return len(flat)


def main():
    OUT.mkdir(exist_ok=True)
    sections, summary = parse_config()
    total = sum(summary.values())
    print(f"[config] секций: {len(summary)}, сущностей: {total} → data/config.json "
          f"({(OUT / 'config.json').stat().st_size // 1024} КБ)")
    for k, n in list(summary.items())[:20]:
        print(f"    {k}: {n}")
    for lang in ("ru", "en"):
        n = parse_locale(lang)
        print(f"[locale] {lang}: строк {n} → data/locale_{lang}.json")


if __name__ == "__main__":
    main()
