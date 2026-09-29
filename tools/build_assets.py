#!/usr/bin/env python3
"""Сбор под браузер: весь конвейер ассетов одной командой и архивы для GitHub Release.

Шаги по порядку — отдельные инструменты из tools/, здесь только их вызов:
decode_textures (WebP) → convert_atlases (спрайт-листы и индекс кадров) → visuals_to_json
(анимации) → ccbi_to_json (макеты UI) → шрифты TTF как есть.

    python3 tools/build_assets.py                          # raw/ → assets/
    python3 tools/build_assets.py --pack dist/             # + архивы и manifest.json для релиза
    python3 tools/build_assets.py --no-build --pack dist/  # только упаковать готовый assets/
Вход  : raw/ (tools/extract_xapk.py)
Выход : assets/; с --pack — dist/underfire-assets-json.tar.gz (всё, кроме WebP: JSON, шрифты,
        PNG), dist/underfire-assets-webp.tar (страницы текстур) и dist/manifest.json (версия
        игры, коммит, число файлов, размеры, sha256). Выкладка — gh release upload (README).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from fetch_assets import ARCHIVES, MANIFEST, sha256

ROOT = Path(__file__).resolve().parents[1]
GAME = {"package": "mobi.rjg.underfire", "version": "1.3.12"}
LAYERS = ("apk", "obb_main", "obb_patch")           # по возрастанию приоритета


def copy_fonts(raw: Path, out: Path) -> int:
    """Шрифты TTF всех слоёв (patch перекрывает main) → out/fonts/."""
    fonts: dict[str, Path] = {}
    for layer in LAYERS:
        for path in sorted((raw / layer / "assets" / "fonts").glob("*.ttf")):
            fonts[path.name] = path
    (out / "fonts").mkdir(parents=True, exist_ok=True)
    for name, src in fonts.items():
        shutil.copy2(src, out / "fonts" / name)
    return len(fonts)


def build(raw: Path, out: Path) -> None:
    import ccbi_to_json
    import convert_atlases
    import decode_textures
    import visuals_to_json

    common = ["--raw", str(raw), "--out"]
    steps = [
        ("текстуры", decode_textures.main, common + [str(out)]),
        ("атласы", convert_atlases.main, common + [str(out)]),
        ("анимации", visuals_to_json.main, common + [str(out)]),
        ("макеты UI", ccbi_to_json.main, common + [str(out / "ui")]),
    ]
    for title, step, argv in steps:
        print(f"[build] {title} …", flush=True)
        if step(argv):
            raise SystemExit(f"[build] шаг «{title}» завершился с ошибкой")
    print(f"[build] шрифты: {copy_fonts(raw, out)} → {out / 'fonts'}")


def part_of(path: Path) -> str:
    return "webp" if path.suffix == ".webp" else "json"


def _clean(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Архив не зависит от машины: без владельца и времени изменения."""
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info


def pack(assets: Path, dist: Path) -> dict:
    """assets/ → архивы частей и manifest.json в dist/. Возвращает manifest."""
    dist.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in assets.rglob("*") if p.is_file() and p.name != MANIFEST)
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = ""
    manifest = {"game": GAME, "commit": commit, "built": datetime.now(UTC).strftime("%Y-%m-%d"),
                "parts": {}}
    for part, name in ARCHIVES.items():
        chosen = [p for p in files if part_of(p) == part]
        archive = dist / name
        with tarfile.open(archive, "w:gz" if name.endswith(".gz") else "w") as tar:
            for p in chosen:
                tar.add(p, arcname=p.relative_to(assets).as_posix(), filter=_clean)
        manifest["parts"][part] = {
            "file": name, "files": len(chosen), "bytes": sum(p.stat().st_size for p in chosen),
            "size": archive.stat().st_size, "sha256": sha256(archive)}
        size = archive.stat().st_size / 1e6
        print(f"[pack] {part}: файлов {len(chosen)}, архив {size:.0f} МБ → {archive}")
    (dist / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Весь конвейер ассетов и архивы для Release")
    ap.add_argument("--raw", type=Path, default=ROOT / "raw", help="распакованный оригинал (raw/)")
    ap.add_argument("--out", type=Path, default=ROOT / "assets", help="куда собирать (assets/)")
    ap.add_argument("--no-build", action="store_true", help="не собирать, только упаковать")
    ap.add_argument("--pack", type=Path, metavar="DIR", help="упаковать архивы и manifest в DIR")
    args = ap.parse_args(argv)
    if not args.no_build:
        build(args.raw, args.out)
    if args.pack:
        pack(args.out, args.pack)
    return 0


if __name__ == "__main__":
    sys.exit(main())
