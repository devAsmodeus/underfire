#!/usr/bin/env python3
"""Сбор под браузер, шаг 2: текстуры *.pkm.ccz (ETC1 в zlib-контейнере) → WebP.

Цепочка: CCZ (16 байт заголовка «CCZ!», дальше zlib) → PKM 1.0 → ETC1 → RGB. ETC1 не хранит
прозрачность, поэтому у большинства текстур закодированная высота вдвое больше исходной: сверху цвет,
снизу альфа-маска в канале R (так её читает шейдер ETC-альфы в libinferno.so). Результат обрезается
до исходного размера из заголовка PKM. Цвет не премультиплицируется: PixiJS 8 делает это сам при
загрузке (alphaMode premultiply-alpha-on-upload). Если маска целиком 255 (карты, фоны) или её нет, WebP
пишется без альфа-канала.

Слои raw/ перекрываются по относительному пути: patch поверх main, main поверх apk.

    python3 tools/decode_textures.py [--raw raw/] [--out assets/] [--only GLOB ...] [--force] [--jobs N]
Вход  : raw/{apk,obb_main,obb_patch}/assets/**/*.pkm.ccz
Выход : assets/<путь без .pkm.ccz>.webp — WebP q90 (например,
        assets/textures_etc/buildings/crate_pret_3_1/w.webp); файлы новее исходника пропускаются
        (--force — перезаписать). --only сверяется с путём от assets/, например
        --only 'textures_etc/units/bomb_pig/*'.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import struct
import sys
import time
import zlib
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import texture2ddecoder
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("apk", "obb_main", "obb_patch")           # по возрастанию приоритета
SUFFIX = ".pkm.ccz"
QUALITY = 90

# Декодер ETC1: (данные, ширина, высота) → пиксели BGRA, 4 байта на пиксель. Параметр — для тестов.
Decoder = Callable[[bytes, int, int], bytes]


def layered_files(raw: Path, suffix: str, sub: str = "") -> dict[str, Path]:
    """Файлы с таким окончанием во всех слоях raw/: путь от assets/ → файл верхнего слоя."""
    found: dict[str, Path] = {}
    for layer in LAYERS:
        base = raw / layer / "assets"
        top = base / sub if sub else base
        if top.is_dir():
            for path in top.rglob("*" + suffix):
                if path.is_file():
                    found[path.relative_to(base).as_posix()] = path
    return dict(sorted(found.items()))


def layer_of(raw: Path, path: Path) -> str:
    """Из какого слоя raw/ этот файл: apk, obb_main или obb_patch."""
    return path.relative_to(raw).parts[0]


def read_ccz(blob: bytes) -> bytes:
    """CCZ: «CCZ!», тип сжатия (0 — zlib), версия, резерв, длина распакованного; дальше zlib."""
    if blob[:4] != b"CCZ!":
        raise ValueError(f"не CCZ: сигнатура {blob[:4]!r}")
    kind, _version, _reserved, length = struct.unpack(">HHII", blob[4:16])
    if kind != 0:
        raise ValueError(f"CCZ: тип сжатия {kind}, поддерживается только zlib (0)")
    data = zlib.decompress(blob[16:])
    if len(data) != length:
        raise ValueError(f"CCZ: распаковано {len(data)} байт, в заголовке {length}")
    return data


@dataclass(frozen=True)
class Pkm:
    """Текстура PKM: закодированный размер (кратен 4), исходный размер и данные ETC1."""

    width: int
    height: int
    orig_width: int
    orig_height: int
    payload: bytes

    @property
    def alpha_below(self) -> bool:
        """Альфа-маска в нижней половине: закодированная высота ровно вдвое больше исходной."""
        return self.height == 2 * self.orig_height


def parse_pkm(data: bytes) -> Pkm:
    """PKM 1.0: «PKM 10», формат (0 — ETC1 RGB), закодированные и исходные ширина и высота."""
    if data[:6] != b"PKM 10":
        raise ValueError(f"не PKM 1.0: сигнатура {data[:6]!r}")
    fmt, width, height, orig_width, orig_height = struct.unpack(">HHHHH", data[6:16])
    if fmt != 0:
        raise ValueError(f"PKM: формат {fmt}, поддерживается только ETC1 RGB (0)")
    if not (0 < orig_width <= width and 0 < orig_height <= height):
        raise ValueError(f"PKM: исходный размер {orig_width}×{orig_height} "
                         f"не помещается в закодированный {width}×{height}")
    need = ((width + 3) // 4) * ((height + 3) // 4) * 8  # блок ETC1 4×4 — 8 байт
    if len(data) - 16 < need:
        raise ValueError(f"PKM: данных {len(data) - 16} байт, для {width}×{height} нужно {need}")
    return Pkm(width, height, orig_width, orig_height, data[16:16 + need])


def pkm_size(path: Path) -> tuple[int, int]:
    """Исходный размер текстуры *.pkm.ccz из заголовка PKM, без распаковки всей текстуры."""
    unzip = zlib.decompressobj()
    head = b""
    with path.open("rb") as fh:
        if fh.read(16)[:4] != b"CCZ!":
            raise ValueError(f"{path}: не CCZ")
        while len(head) < 16:
            chunk = fh.read(1 << 16)
            if not chunk and not unzip.unconsumed_tail:
                raise ValueError(f"{path}: обрыв данных в заголовке PKM")
            head += unzip.decompress(unzip.unconsumed_tail + chunk, 16 - len(head))
    pkm = struct.unpack(">6sHHHHH", head)
    if pkm[0] != b"PKM 10":
        raise ValueError(f"{path}: не PKM 1.0")
    return pkm[4], pkm[5]


def etc1_decoder(payload: bytes, width: int, height: int) -> bytes:
    """ETC1 → BGRA через texture2ddecoder."""
    return texture2ddecoder.decode_etc1(payload, width, height)


def to_image(pkm: Pkm, decode: Decoder = etc1_decoder) -> Image.Image:
    """Цвет из верхней половины, альфа — канал R нижней; обрезка до исходного размера.
    Возвращает RGBA или RGB, если маски нет или она целиком 255."""
    pixels = decode(pkm.payload, pkm.width, pkm.height)
    full = Image.frombuffer("RGBA", (pkm.width, pkm.height), pixels, "raw", "BGRA", 0, 1)
    w, h = pkm.orig_width, pkm.orig_height
    color = full.crop((0, 0, w, h)).convert("RGB")
    if not pkm.alpha_below:
        return color
    alpha = full.crop((0, h, w, 2 * h)).getchannel("R")
    if alpha.getextrema() == (255, 255):
        return color
    color.putalpha(alpha)
    return color


def out_path(out: Path, rel: str) -> Path:
    """textures_etc/…/w.pkm.ccz → <out>/textures_etc/…/w.webp."""
    return out / (rel[: -len(SUFFIX)] + ".webp")


def convert(src: Path, dst: Path, decode: Decoder = etc1_decoder) -> str:
    """Одна текстура → WebP (через временный файл, чтобы обрыв не оставил «актуальный» мусор).
    Возвращает режим результата: RGBA или RGB."""
    img = to_image(parse_pkm(read_ccz(src.read_bytes())), decode)
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    try:
        img.save(part, "WEBP", quality=QUALITY)
        os.replace(part, dst)
    finally:
        part.unlink(missing_ok=True)
    return img.mode


def _task(task: tuple[str, Path, Path], decode: Decoder = etc1_decoder
          ) -> tuple[str, str | None, str | None]:
    """Задача прогона: (путь, режим или None, ошибка или None). Ошибка одной текстуры не роняет
    весь прогон — они копятся и печатаются в конце."""
    rel, src, dst = task
    try:
        return rel, convert(src, dst, decode), None
    except Exception as e:
        return rel, None, f"{type(e).__name__}: {e}"


@dataclass
class Summary:
    selected: int = 0
    written: int = 0
    skipped: int = 0
    rgba: int = 0
    rgb: int = 0
    bytes: int = 0          # объём WebP всех выбранных текстур (записанных и актуальных)
    seconds: float = 0.0
    errors: dict[str, str] = field(default_factory=dict)   # путь → текст ошибки


def select(files: dict[str, Path], only: Iterable[str] = ()) -> dict[str, Path]:
    """Фильтр --only: путь от assets/ должен подойти хотя бы под один шаблон."""
    only = list(only)
    if not only:
        return files
    return {rel: p for rel, p in files.items() if any(fnmatch.fnmatchcase(rel, g) for g in only)}


def decode_all(raw: Path, out: Path, only: Iterable[str] = (), force: bool = False, jobs: int = 1,
               decode: Decoder = etc1_decoder) -> Summary:
    """Все текстуры raw/ (с учётом слоёв) → WebP в out/. jobs > 1 — пул процессов (только со
    штатным декодером: фейковый в другой процесс не передать)."""
    started = time.monotonic()
    files = select(layered_files(raw, SUFFIX), only)
    s = Summary(selected=len(files))
    todo = []
    for rel, src in files.items():
        dst = out_path(out, rel)
        if not force and dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            s.skipped += 1
        else:
            todo.append((rel, src, dst))
    if jobs > 1 and decode is etc1_decoder and len(todo) > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(_task, todo, chunksize=4))
    else:
        results = [_task(task, decode) for task in todo]
    for rel, mode, error in results:
        if error:
            s.errors[rel] = error
        else:
            s.written += 1
            s.rgba += mode == "RGBA"
            s.rgb += mode == "RGB"
    for rel in files:
        dst = out_path(out, rel)
        if rel not in s.errors and dst.exists():
            s.bytes += dst.stat().st_size
    s.seconds = time.monotonic() - started
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Текстуры *.pkm.ccz (ETC1) → WebP")
    ap.add_argument("--raw", type=Path, default=ROOT / "raw", help="распакованный оригинал (raw/)")
    ap.add_argument("--out", type=Path, default=ROOT / "assets", help="куда писать (assets/)")
    ap.add_argument("--only", action="append", default=[], metavar="GLOB",
                    help="только текстуры, чей путь от assets/ подходит под шаблон; можно несколько")
    ap.add_argument("--force", action="store_true", help="перезаписать уже актуальные файлы")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1,
                    help="число процессов (по умолчанию — все ядра)")
    args = ap.parse_args(argv)
    s = decode_all(args.raw, args.out, args.only, args.force, max(1, args.jobs))
    for rel, error in sorted(s.errors.items()):
        print(f"[textures] ошибка: {rel}: {error}", file=sys.stderr)
    print(f"[textures] текстур: {s.selected}, записано {s.written} (RGBA {s.rgba}, RGB {s.rgb}), "
          f"актуальных {s.skipped}, ошибок {len(s.errors)}; WebP {s.bytes / 1e6:.1f} МБ → {args.out}; "
          f"{s.seconds:.0f} с")
    return 1 if s.errors else 0


if __name__ == "__main__":
    sys.exit(main())
