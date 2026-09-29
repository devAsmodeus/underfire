#!/usr/bin/env python3
"""Сбор под браузер, шаг 4: анимации config/visuals/**/*.xml → JSON.

Формат XML (его читает CRjObjectBuilder::addMapObjectVisualInfoFromXML в libinferno.so):
visual(name, fps, scale, atlases) → directions/direction(name, prefix, atlases, offsetX, offsetY,
width, height, hitArea) → states/state(name) → layers/layer(frameCount, frames="1,3,5,").

Выход — assets/visuals/<путь от config/visuals без .xml>.json:
  name        имя набора текстур и начало имён кадров;
  fps, scale  15 и 1 почти везде (по умолчанию в движке 30 и 1);
  atlases     JSON атласов (от assets/), которые движок грузит для всего визуала:
              textures_etc/<категория визуала>/<name>/<атлас>;
  directions  имя направления → {prefix, mirror, offsetX, offsetY, width, height, atlases,
              [hitArea], states}:
    prefix    чьи кадры рисовать; mirror = (name ≠ prefix): у юнитов n, w, nw рисуются
              отражёнными e, s, se — движок ставит им scaleX = −1;
    atlases   атласы только этого направления: textures_etc/buildings/<name>/<prefix>/<атлас>;
    hitArea   плоский список x0, y0, x1, y1, … как в XML (отрезки подряд, многоугольник проверяется
              по правилу чёт-нечет) — от точки объекта, ось Y вниз, умножать на scale, как и offset;
    states    имя состояния → слои по порядку, каждый следующий поверх предыдущего:
              [{frameCount, frames: [номера кадров]}].
Атласы на запрос «X» выбираются, как в движке (convert_atlases.page_set): X или страницы X_1, X_2…

Имя кадра: f"{name}_{prefix}_{номер}.png" — ровно так его строит движок (с «/» в начале, которого
в наших атласах нет). Кадры ищутся в атласах визуала и в assets/frames_index.json; сводка в конце
говорит, сколько не нашлось.

Отрисовка слоя (RjAnimationLayer::run): спрайт кадра с anchor (0, 0), масштаб (sx, s), позиция
(trunc(offsetX·sx), trunc(offsetY·s)) от точки объекта, ось Y вниз; s = scale, sx = −s при mirror,
иначе s. Кадр держится 1/fps с; если номеров меньше frameCount, повторяется последний, лишние не
показываются. Если какого-то кадра нет в загруженных атласах, движок не показывает слой целиком.

    python3 tools/visuals_to_json.py [--raw raw/] [--out assets/]
Вход  : raw/{apk,obb_main,obb_patch}/assets/config/visuals/**/*.xml (слои перекрываются, как в
        decode_textures.py); атласы и frames_index.json в assets/ — сначала convert_atlases.py
Выход : assets/visuals/**/*.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from convert_atlases import ATLAS, page_set, write_json
from decode_textures import ROOT, SUFFIX, layer_of, layered_files

VISUALS = "config/visuals"


def _ints(text: str | None, where: str) -> list[int]:
    """«1,3,5,» → [1, 3, 5]: пустые элементы (хвостовая запятая) пропускаются, как в движке."""
    items = [t.strip() for t in (text or "").split(",") if t.strip()]
    try:
        return [int(t) for t in items]
    except ValueError:
        raise ValueError(f"{where}: не число в {text!r}") from None


def _names(text: str | None) -> list[str]:
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def parse_visual(text: str, where: str = "visual") -> dict:
    """XML визуала → словарь с полями как в выходном JSON, но с именами атласов из XML."""
    root = ET.fromstring(text)
    if root.tag != "visual":
        raise ValueError(f"{where}: корень <{root.tag}>, ожидался <visual>")
    directions = {}
    for d in root.iterfind("directions/direction"):
        name, prefix = d.get("name", ""), d.get("prefix", "")
        at = f"{where}: direction {name}"
        states = {}
        for st in d.iterfind("states/state"):
            states[st.get("name", "")] = [
                {"frameCount": int(layer.get("frameCount", "0")),
                 "frames": _ints(layer.get("frames"), f"{at}/{st.get('name')}")}
                for layer in st.iterfind("layers/layer")]
        entry = {
            "prefix": prefix,
            "mirror": name != prefix,
            "offsetX": int(d.get("offsetX", "0")),
            "offsetY": int(d.get("offsetY", "0")),
            "width": int(d.get("width", "0")),
            "height": int(d.get("height", "0")),
            "atlases": _names(d.get("atlases")),
        }
        if hit := _ints(d.get("hitArea"), f"{at}/hitArea"):
            entry["hitArea"] = hit
        entry["states"] = states
        directions[name] = entry
    return {
        "name": root.get("name", ""),
        "fps": int(root.get("fps", "30")),
        "scale": float(root.get("scale", "1")),
        "atlases": _names(root.get("atlases")),
        "directions": directions,
    }


def frame_name(name: str, prefix: str, number: int) -> str:
    """Имя кадра в атласе: <name>_<prefix>_<номер>.png."""
    return f"{name}_{prefix}_{number}.png"


def resolve_atlases(visual: dict, category: str, stems: set[str], in_patch: set[str]
                    ) -> tuple[dict, list[str]]:
    """Имена атласов из XML → пути JSON от assets/ по правилу движка. Возвращает визуал с путями
    и список запросов, по которым не нашлось ни одного атласа."""
    missing = []

    def pages(base: str) -> list[str]:
        found = page_set(base, stems, in_patch)
        if not found:
            missing.append(base)
        return [p + ".json" for p in found]

    name = visual["name"]
    out = dict(visual, atlases=[p for a in visual["atlases"]
                                for p in pages(f"textures_etc/{category}/{name}/{a}")])
    out["directions"] = {
        d: dict(e, atlases=[p for a in e["atlases"]
                            for p in pages(f"textures_etc/buildings/{name}/{e['prefix']}/{a}")])
        for d, e in visual["directions"].items()}
    return out, missing


@dataclass
class Summary:
    visuals: int = 0
    directions: int = 0
    mirrored: dict[str, int] = field(default_factory=dict)      # «n→e» → сколько
    frames: int = 0                                             # уникальных имён кадров
    not_in_index: int = 0
    not_in_own: int = 0                                         # нет в атласах самого визуала
    index_elsewhere: int = 0            # в индексе есть, но он указывает на чужой атлас
    visuals_missing: dict[str, int] = field(default_factory=dict)   # визуал → кадров нет в индексе
    visuals_elsewhere: dict[str, int] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)         # запросы атласов без файлов
    errors: dict[str, str] = field(default_factory=dict)
    seconds: float = 0.0


def convert_all(raw: Path, out: Path) -> Summary:
    """Все визуалы raw/ → JSON в out/visuals/ со сверкой кадров по атласам и индексу из out/."""
    started = time.monotonic()
    s = Summary()
    index_path = out / "frames_index.json"
    if not index_path.is_file():
        raise SystemExit(f"нет {index_path} — сначала tools/convert_atlases.py")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    stems = {rel[: -len(ATLAS)] for rel in layered_files(raw, ATLAS, "textures_etc")}
    in_patch = {rel[: -len(SUFFIX)] for rel, p in layered_files(raw, SUFFIX, "textures_etc").items()
                if layer_of(raw, p) == "obb_patch"}
    sheets: dict[str, set[str]] = {}

    def frames_of(sheet: str) -> set[str]:
        if sheet not in sheets:
            path = out / sheet
            sheets[sheet] = (set(json.loads(path.read_text(encoding="utf-8"))["frames"])
                             if path.is_file() else set())
        return sheets[sheet]

    for rel, src in layered_files(raw, ".xml", VISUALS).items():
        key = rel[len(VISUALS) + 1: -len(".xml")]               # units/bomb_pig
        category = key.rsplit("/", 1)[0] if "/" in key else "units"   # как в движке
        try:
            parsed = parse_visual(src.read_text(encoding="utf-8"), rel)
        except (ET.ParseError, ValueError) as e:
            s.errors[rel] = str(e)
            continue
        visual, missing = resolve_atlases(parsed, category, stems, in_patch)
        write_json(out / "visuals" / f"{key}.json", visual)
        s.visuals += 1
        s.unresolved += [f"{key}: {m}" for m in missing]
        names: dict[str, set[str]] = {}                          # кадр → атласы визуала
        for d, e in visual["directions"].items():
            s.directions += 1
            if e["mirror"]:
                pair = f"{d}→{e['prefix']}"
                s.mirrored[pair] = s.mirrored.get(pair, 0) + 1
            own = set(visual["atlases"]) | set(e["atlases"])
            for layers in e["states"].values():
                for layer in layers:
                    for n in layer["frames"]:
                        names.setdefault(frame_name(visual["name"], e["prefix"], n), set()).update(own)
        lost = elsewhere = 0
        for name, own in names.items():
            in_own = any(name in frames_of(sheet) for sheet in own)
            s.not_in_own += not in_own
            if name not in index:
                lost += 1
            elif in_own and index[name] not in own:
                elsewhere += 1
        s.frames += len(names)
        s.not_in_index += lost
        s.index_elsewhere += elsewhere
        if lost:
            s.visuals_missing[key] = lost
        if elsewhere:
            s.visuals_elsewhere[key] = elsewhere
    s.seconds = time.monotonic() - started
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Анимации config/visuals/**/*.xml → JSON")
    ap.add_argument("--raw", type=Path, default=ROOT / "raw", help="распакованный оригинал (raw/)")
    ap.add_argument("--out", type=Path, default=ROOT / "assets",
                    help="assets/: здесь атласы и frames_index.json, сюда пишется visuals/")
    args = ap.parse_args(argv)
    s = convert_all(args.raw, args.out)
    for rel, error in sorted(s.errors.items()):
        print(f"[visuals] ошибка: {rel}: {error}", file=sys.stderr)
    for item in s.unresolved:
        print(f"[visuals] нет атласа: {item}")
    top = sorted(s.visuals_missing.items(), key=lambda kv: (-kv[1], kv[0]))
    for key, n in top[:20]:
        print(f"[visuals] кадров нет в индексе: {key}: {n}")
    if len(top) > 20:
        print(f"[visuals] … и ещё {len(top) - 20} визуалов")
    mirrored = ", ".join(f"{k} {v}" for k, v in sorted(s.mirrored.items()))
    print(f"[visuals] визуалов: {s.visuals}, направлений: {s.directions} (отражённых: {mirrored or 0}), "
          f"ошибок {len(s.errors)}; {s.seconds:.0f} с")
    print(f"[visuals] кадров (уникальных имён по визуалам): {s.frames}; нет в frames_index.json: "
          f"{s.not_in_index} ({len(s.visuals_missing)} визуалов); нет в атласах самого визуала: "
          f"{s.not_in_own}; индекс указывает на чужой атлас: {s.index_elsewhere} "
          f"({len(s.visuals_elsewhere)} визуалов); запросов атласов без файлов: {len(s.unresolved)}")
    return 1 if s.errors else 0


if __name__ == "__main__":
    sys.exit(main())
