#!/usr/bin/env python3
"""Готовые ассеты без XAPK: скачать архивы из GitHub Release и распаковать в assets/.

Архивы собирает tools/build_assets.py --pack у того, у кого есть raw/; этот скрипт нужен всем
остальным — сессиям и машинам без оригинала игры. Только стандартная библиотека: запускается
до pip install.

    python3 tools/fetch_assets.py                    # всё: JSON (≈50 МБ в распаковке) + WebP (≈400 МБ)
    python3 tools/fetch_assets.py --only json        # без текстур: атласы, визуалы, макеты UI, шрифты
Вход  : https://github.com/devAsmodeus/underfire/releases/tag/<tag> — manifest.json и архивы
Выход : assets/ — как после tools/build_assets.py; sha256 архивов сверяется с manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "devAsmodeus/underfire"
TAG = "assets-v1.3.12"
MANIFEST = "manifest.json"
# Части комплекта: имя → архив. WebP уже сжат, поэтому его tar без gzip.
ARCHIVES = {"json": "underfire-assets-json.tar.gz", "webp": "underfire-assets-webp.tar"}


def _get(url: str, dst: Path) -> None:
    """Скачать url в dst. Если Python не доверяет сертификатам сайта (так бывает у сборки
    с python.org на macOS без Install Certificates.command), качаем через curl — он берёт
    системные сертификаты."""
    req = urllib.request.Request(url, headers={"User-Agent": "underfire-fetch-assets"})
    try:
        with urllib.request.urlopen(req) as res, dst.open("wb") as f:
            shutil.copyfileobj(res, f, 1 << 20)
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError) or not shutil.which("curl"):
            raise
        subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", str(dst), url], check=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(base_url: str, out: Path, parts: list[str]) -> dict:
    """Скачать manifest и выбранные части, проверить sha256, распаковать в out. Возвращает manifest."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        _get(base_url + MANIFEST, tmp_dir / MANIFEST)
        manifest = json.loads((tmp_dir / MANIFEST).read_text(encoding="utf-8"))
        out.mkdir(parents=True, exist_ok=True)
        for part in parts:
            info = manifest["parts"][part]
            archive = tmp_dir / info["file"]
            print(f"[assets] {part}: {info['file']} ({info['size'] / 1e6:.0f} МБ) …", flush=True)
            _get(base_url + info["file"], archive)
            if sha256(archive) != info["sha256"]:
                raise SystemExit(f"{info['file']}: sha256 не совпал с {MANIFEST} — архив повреждён")
            with tarfile.open(archive) as tar:
                tar.extractall(out, filter="data")   # filter="data": без путей за пределы out
            print(f"[assets] {part}: файлов {info['files']} → {out}")
        (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ассеты из GitHub Release → assets/")
    ap.add_argument("--tag", default=TAG, help=f"релиз (по умолчанию {TAG})")
    ap.add_argument("--repo", default=REPO, help=f"репозиторий (по умолчанию {REPO})")
    ap.add_argument("--base-url", help="откуда качать вместо релиза (для зеркал и тестов)")
    ap.add_argument("--only", action="append", choices=sorted(ARCHIVES), help="только эта часть")
    ap.add_argument("--out", type=Path, default=ROOT / "assets", help="куда распаковать (assets/)")
    args = ap.parse_args(argv)
    base = args.base_url or f"https://github.com/{args.repo}/releases/download/{args.tag}/"
    manifest = fetch(base if base.endswith("/") else base + "/", args.out, args.only or list(ARCHIVES))
    game = manifest.get("game", {})
    print(f"[assets] готово: {game.get('package')} {game.get('version')}, "
          f"сборка {manifest.get('built')} из {manifest.get('commit', '?')[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
