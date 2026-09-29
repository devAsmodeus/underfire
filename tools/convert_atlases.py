#!/usr/bin/env python3
"""Сбор под браузер, шаг 3: атласы Inferno *.atlas → JSON спрайт-листов PixiJS 8.

Формат .atlas: строка «textures: <имя>.png», дальше по строке на кадр через табуляцию: имя, x y w h
(прямоугольник на странице), ox oy (смещение обрезанного кадра от левого верхнего угла исходного),
W H (исходный размер) и необязательный флаг r. Кадр с r лежит на странице повёрнутым на 90° по часовой,
а пары w,h и ox,oy у него записаны в повёрнутом виде: настоящий размер — h×w, смещение — (oy, ox).

Выход — TexturePacker JSON-hash в том виде, как его читает PixiJS 8 (Spritesheet._processFrames):
  frame             {x, y, w, h}; w и h — в неповёрнутом виде: у повёрнутого кадра Pixi сам берёт на
                    странице прямоугольник (x, y, h, w);
  rotated           true у кадров с r; Pixi ставит им Texture.rotate = 2, то есть считает, что кадр
                    хранится повёрнутым на 90° по часовой, — то же соглашение, что у Inferno;
  trimmed, spriteSourceSize {x, y, w, h} (обрезанный кадр внутри исходного), sourceSize {w, h};
  meta              {image, size, scale}.
Имена кадров — как в .atlas, без ведущего «/». Пустые кадры (w или h = 0) сохраняются как есть.

Аномалии:
  - страница ищется по имени файла атласа (<имя>.pkm.ccz → <имя>.webp из decode_textures.py), а не по
    заголовку: у maps/city/cells.atlas в заголовке atlas.png;
  - effects/tracers/tracers.atlas ссылается на обычный tracers.png (движок берёт для «tracers» .png
    вместо .pkm.ccz) — он копируется рядом с JSON как есть;
  - кадры, выходящие за край страницы (interface/*/city/tutorial_menu), обрезаются по краю, исходный
    размер кадра не меняется.

Индексы (пути — от assets/):
  frames_index.json     имя кадра → JSON атласа; если имя есть и в HD-, и в SD-наборе интерфейса
                        (textures_etc/interface/1024x768_sd), здесь HD-вариант;
  frames_index_sd.json  SD-варианты таких имён.
  В индексы не входят атласы, которые движок не загружает: при X.atlas и страницах X_1, X_2… в одной
  папке он берёт только один вариант (см. page_set). Если кандидатов всё равно несколько (одно имя в
  разных папках, например citizens/bug и mobs/bug), в индексе первый по пути.

    python3 tools/convert_atlases.py [--raw raw/] [--out assets/]
Вход  : raw/{apk,obb_main,obb_patch}/assets/textures_etc/**/*.atlas (+ заголовки *.pkm.ccz — размер
        страницы); слои перекрываются так же, как в decode_textures.py
Выход : assets/<путь без .atlas>.json рядом с WebP страницы, assets/frames_index.json,
        assets/frames_index_sd.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from decode_textures import ROOT, SUFFIX, layer_of, layered_files, pkm_size
from PIL import Image

ATLAS = ".atlas"
SD = "textures_etc/interface/1024x768_sd/"          # SD-набор интерфейса


@dataclass(frozen=True)
class Frame:
    """Строка .atlas; x y w h ox oy — как записаны (у повёрнутого кадра — в повёрнутом виде)."""

    name: str
    x: int
    y: int
    w: int
    h: int
    ox: int
    oy: int
    src_w: int
    src_h: int
    rotated: bool = False


def parse_atlas(text: str, where: str = "atlas") -> tuple[str, list[Frame]]:
    """Текст .atlas → (страница из заголовка, кадры). Имена — без ведущего «/»."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or not lines[0].startswith("textures:"):
        raise ValueError(f"{where}: нет заголовка «textures:»")
    page = lines[0].split(":", 1)[1].strip()
    frames = []
    for n, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        parts = line.split("\t")
        while parts and not parts[-1].strip():
            parts.pop()
        rotated = len(parts) == 10 and parts[9].strip() == "r"
        if len(parts) != 9 + rotated:
            raise ValueError(f"{where}:{n}: ожидалось 9 полей и флаг r, получено {parts!r}")
        try:
            x, y, w, h, ox, oy, src_w, src_h = (int(v) for v in parts[1:9])
        except ValueError:
            raise ValueError(f"{where}:{n}: не число в {parts[1:9]!r}") from None
        frames.append(Frame(parts[0].lstrip("/"), x, y, w, h, ox, oy, src_w, src_h, rotated))
    return page, frames


def pixi_frame(f: Frame, page_w: int, page_h: int) -> tuple[dict, bool]:
    """Кадр Inferno → запись JSON-hash для PixiJS 8. Второе значение — обрезан ли кадр по краю
    страницы: срезанные столбцы и строки становятся прозрачными, исходный размер тот же."""
    w = max(0, min(f.w, page_w - f.x))
    h = max(0, min(f.h, page_h - f.y))
    if f.rotated:
        # Кадр повёрнут на 90° по часовой: правые столбцы прямоугольника на странице — его верхние
        # строки, нижние строки — правые столбцы. Срез справа сдвигает кадр вниз, срез снизу сужает.
        dw, dh, dx, dy = h, w, f.oy, f.ox + (f.w - w)
    else:
        dw, dh, dx, dy = w, h, f.ox, f.oy
    return {
        "frame": {"x": f.x, "y": f.y, "w": dw, "h": dh},
        "rotated": f.rotated,
        "trimmed": (dx, dy, dw, dh) != (0, 0, f.src_w, f.src_h),
        "spriteSourceSize": {"x": dx, "y": dy, "w": dw, "h": dh},
        "sourceSize": {"w": f.src_w, "h": f.src_h},
    }, (w, h) != (f.w, f.h)


def sheet(frames: list[Frame], image: str, page: tuple[int, int], where: str = "atlas"
          ) -> tuple[dict, list[str]]:
    """Кадры → JSON спрайт-листа; второе значение — имена кадров, обрезанных по краю страницы."""
    out: dict[str, dict] = {}
    clipped = []
    for f in frames:
        if f.name in out:
            raise ValueError(f"{where}: кадр {f.name} встречается дважды")
        out[f.name], cut = pixi_frame(f, *page)
        if cut:
            clipped.append(f.name)
    meta = {"image": image, "size": {"w": page[0], "h": page[1]}, "scale": "1"}
    return {"frames": out, "meta": meta}, clipped


def page_set(stem: str, stems: set[str], in_patch: set[str]) -> list[str]:
    """Какие атласы движок загрузит по запросу stem (RjUtils::addSpriteFramesWithFile в libinferno):
    сам stem, если его текстура лежит в patch; иначе страницы stem_1, stem_2… подряд, пока есть;
    если страниц нет — снова stem. Имена — пути без расширения."""
    if stem in stems and stem in in_patch:
        return [stem]
    pages: list[str] = []
    while f"{stem}_{len(pages) + 1}" in stems:
        pages.append(f"{stem}_{len(pages) + 1}")
    return pages or ([stem] if stem in stems else [])


def shadowed(stems: set[str], in_patch: set[str]) -> set[str]:
    """Атласы, которые движок не загружает: из пары «X и страницы X_1, X_2…» остаётся один вариант."""
    hidden: set[str] = set()
    for stem in stems:
        if f"{stem}_1" in stems:
            pages = {p for p in stems if p.startswith(stem + "_") and p[len(stem) + 1:].isdigit()}
            hidden |= ({stem} | pages) - set(page_set(stem, stems, in_patch))
    return hidden


def build_indexes(sheets: dict[str, dict], hidden: set[str]) -> tuple[dict, dict, dict]:
    """sheets: путь JSON атласа от assets/ → JSON. Возвращает (индекс, SD-индекс, статистику)."""
    candidates: dict[str, list[str]] = {}
    for path in sorted(sheets):
        if path[: -len(".json")] not in hidden:
            for name in sheets[path]["frames"]:
                candidates.setdefault(name, []).append(path)
    index, index_sd = {}, {}
    stats = {"ambiguous": 0, "ambiguous_same": 0}

    def geometry(path: str, name: str) -> tuple:
        e = sheets[path]["frames"][name]
        return (e["frame"]["w"], e["frame"]["h"], e["rotated"],
                tuple(e["spriteSourceSize"].values()), tuple(e["sourceSize"].values()))

    for name, paths in sorted(candidates.items()):
        hd = [p for p in paths if not p.startswith(SD)]
        sd = [p for p in paths if p.startswith(SD)]
        pick = hd or sd
        index[name] = pick[0]
        if hd and sd:
            index_sd[name] = sd[0]
        if len(pick) > 1:
            stats["ambiguous"] += 1
            stats["ambiguous_same"] += len({geometry(p, name) for p in pick}) == 1
    return index, index_sd, stats


@dataclass
class Summary:
    atlases: int = 0
    frames: int = 0
    rotated: int = 0
    trimmed: int = 0
    empty: int = 0
    clipped: list[str] = field(default_factory=list)       # «атлас: кадр»
    header_mismatch: list[str] = field(default_factory=list)
    plain_pages: list[str] = field(default_factory=list)   # страницы — обычные PNG
    hidden: list[str] = field(default_factory=list)        # атласы вне индексов
    index: int = 0
    index_sd: int = 0
    ambiguous: int = 0
    ambiguous_same: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    seconds: float = 0.0


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def convert_all(raw: Path, out: Path) -> Summary:
    """Все атласы raw/ → JSON в out/ и индексы кадров."""
    started = time.monotonic()
    s = Summary()
    atlases = layered_files(raw, ATLAS, "textures_etc")
    textures = layered_files(raw, SUFFIX, "textures_etc")
    pngs = layered_files(raw, ".png", "textures_etc")
    stems = {rel[: -len(ATLAS)] for rel in atlases}
    in_patch = {rel[: -len(SUFFIX)] for rel, p in textures.items() if layer_of(raw, p) == "obb_patch"}
    hidden = shadowed(stems, in_patch)
    sheets: dict[str, dict] = {}
    for rel, src in atlases.items():
        stem = rel[: -len(ATLAS)]
        try:
            header, frames = parse_atlas(src.read_text(encoding="utf-8"), rel)
            name = Path(stem).name
            if header != name + ".png":
                s.header_mismatch.append(f"{rel}: {header}")
            if stem + SUFFIX in textures:
                image, size = name + ".webp", pkm_size(textures[stem + SUFFIX])
            elif (plain := f"{Path(stem).parent.as_posix()}/{header}") in pngs:
                image = header
                with Image.open(pngs[plain]) as im:
                    size = im.size
                dst = out / plain
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(pngs[plain], dst)
                s.plain_pages.append(f"{rel}: {header}")
            else:
                raise ValueError(f"нет страницы: ни {name}{SUFFIX}, ни {header}")
            data, clipped = sheet(frames, image, size, rel)
        except (OSError, ValueError) as e:
            s.errors[rel] = str(e)
            continue
        write_json(out / (stem + ".json"), data)
        sheets[stem + ".json"] = data
        s.atlases += 1
        s.frames += len(frames)
        s.rotated += sum(f.rotated for f in frames)
        s.empty += sum(f.w == 0 or f.h == 0 for f in frames)
        s.trimmed += sum(e["trimmed"] for e in data["frames"].values())
        s.clipped += [f"{rel}: {c}" for c in clipped]
    index, index_sd, stats = build_indexes(sheets, hidden)
    write_json(out / "frames_index.json", index)
    write_json(out / "frames_index_sd.json", index_sd)
    s.hidden = sorted(h + ATLAS for h in hidden)
    s.index, s.index_sd = len(index), len(index_sd)
    s.ambiguous, s.ambiguous_same = stats["ambiguous"], stats["ambiguous_same"]
    s.seconds = time.monotonic() - started
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Атласы Inferno *.atlas → JSON спрайт-листов PixiJS 8")
    ap.add_argument("--raw", type=Path, default=ROOT / "raw", help="распакованный оригинал (raw/)")
    ap.add_argument("--out", type=Path, default=ROOT / "assets", help="куда писать (assets/)")
    args = ap.parse_args(argv)
    s = convert_all(args.raw, args.out)
    for rel, error in sorted(s.errors.items()):
        print(f"[atlas] ошибка: {rel}: {error}", file=sys.stderr)
    for title, items in (("заголовок не совпадает с именем файла", s.header_mismatch),
                         ("страница — готовый PNG", s.plain_pages),
                         ("кадр обрезан по краю страницы", s.clipped)):
        for item in items:
            print(f"[atlas] {title}: {item}")
    print(f"[atlas] атласов: {s.atlases}, кадров: {s.frames} (повёрнутых {s.rotated}, обрезанных "
          f"{s.trimmed}, пустых {s.empty}), ошибок {len(s.errors)}; {s.seconds:.0f} с")
    print(f"[atlas] frames_index.json: {s.index} имён (в нескольких атласах {s.ambiguous}, из них с "
          f"одинаковой геометрией {s.ambiguous_same}); frames_index_sd.json: {s.index_sd}; "
          f"не загружаются движком и не в индексе: {len(s.hidden)} атласов")
    return 1 if s.errors else 0


if __name__ == "__main__":
    sys.exit(main())
