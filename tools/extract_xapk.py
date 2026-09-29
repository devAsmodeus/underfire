#!/usr/bin/env python3
"""Подготовка данных: XAPK (APKPure) → raw/.

XAPK — zip с APK и двумя OBB. Из APK берём только assets/ (код игры, lib/armeabi/libinferno.so,
не распаковываем), OBB распаковываем целиком: у обоих внутри один корень assets/.

    python3 tools/extract_xapk.py путь/к/Under+Fire_+Invasion_1.3.12_APKPure.xapk [--force]
Выход : raw/apk/assets, raw/obb_main/assets, raw/obb_patch/assets
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE, VERSION = "mobi.rjg.underfire", "1.3.12"
# Сколько файлов даёт v1.3.12 (вместе с .DS_Store из main OBB) — сверка после распаковки.
EXPECTED = {"apk": 160, "obb_main": 8884, "obb_patch": 2932}


def _pick(names: list[str], suffix: str, prefix: str = "") -> str:
    """Единственный файл архива с таким окончанием (и началом имени)."""
    found = [n for n in names if n.endswith(suffix) and Path(n).name.startswith(prefix)]
    if len(found) != 1:
        raise SystemExit(f"в XAPK ожидался ровно один {prefix}*{suffix}, найдено: {found}")
    return found[0]


def extract(xapk: Path, out: Path, force: bool = False) -> dict[str, int]:
    """Распаковывает XAPK в out/{apk,obb_main,obb_patch}; возвращает число файлов в каждой."""
    targets = {"apk": out / "apk", "obb_main": out / "obb_main", "obb_patch": out / "obb_patch"}
    busy = [str(p) for p in targets.values() if p.exists() and any(p.iterdir())]
    if busy and not force:
        raise SystemExit(f"уже распаковано: {', '.join(busy)} — перезаписать: --force")
    with zipfile.ZipFile(xapk) as x, tempfile.TemporaryDirectory() as tmp:
        names = x.namelist()
        if "manifest.json" in names:
            m = json.loads(x.read("manifest.json"))
            got = (m.get("package_name"), m.get("version_name"))
            if got != (PACKAGE, VERSION):
                print(f"[!] manifest.json: {got}, проект рассчитан на {(PACKAGE, VERSION)}",
                      file=sys.stderr)
        layers = [("apk", _pick(names, ".apk"), "assets/"),          # (слой, файл, что брать)
                  ("obb_main", _pick(names, ".obb", "main."), ""),
                  ("obb_patch", _pick(names, ".obb", "patch."), "")]
        for p in targets.values():                                    # архив проверен — чистим
            shutil.rmtree(p, ignore_errors=True)
        counts = {}
        for key, name, prefix in layers:
            inner = Path(x.extract(name, tmp))                        # вложенный zip — на диск
            with zipfile.ZipFile(inner) as z:
                members = [i for i in z.infolist()
                           if not i.is_dir() and i.filename.startswith(prefix)]
                z.extractall(targets[key], members)
            inner.unlink()
            counts[key] = len(members)
    return counts


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="XAPK Under Fire: Invasion → raw/")
    ap.add_argument("xapk", type=Path, help="путь к XAPK mobi.rjg.underfire 1.3.12")
    ap.add_argument("--out", type=Path, default=ROOT / "raw",
                    help="куда распаковать (по умолчанию raw/)")
    ap.add_argument("--force", action="store_true", help="перезаписать уже распакованное")
    args = ap.parse_args(argv)
    for key, n in extract(args.xapk, args.out, args.force).items():
        note = "" if n == EXPECTED[key] else f"  [!] для v{VERSION} ожидалось {EXPECTED[key]}"
        print(f"[xapk] {key}: файлов {n} → {args.out / key}{note}")


if __name__ == "__main__":
    main()
