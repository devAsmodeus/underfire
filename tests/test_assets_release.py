"""Архивы ассетов для Release: упаковка (build_assets) и скачивание (fetch_assets) без сети."""
import json
import tarfile

import build_assets
import fetch_assets
import pytest

FILES = {
    "ui/1024x768/popup.json": b'{"root": {}}',
    "textures_etc/units/pig/pig_1.webp": b"RIFF\x00\x00\x00\x00WEBP",
    "textures_etc/units/pig/pig_1.json": b'{"frames": {}}',
    "fonts/Play.ttf": b"\x00\x01\x00\x00",
    "frames_index.json": b"{}",
}


@pytest.fixture
def dist(tmp_path):
    """Игрушечный assets/, упакованный как для релиза."""
    root = tmp_path / "assets"
    for rel, data in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    out = tmp_path / "dist"
    build_assets.pack(root, out)
    return out


def test_pack_splits_webp_from_the_rest(dist):
    manifest = json.loads((dist / fetch_assets.MANIFEST).read_text())
    assert manifest["game"] == {"package": "mobi.rjg.underfire", "version": "1.3.12"}
    assert (manifest["parts"]["json"]["files"], manifest["parts"]["webp"]["files"]) == (4, 1)
    with tarfile.open(dist / fetch_assets.ARCHIVES["webp"]) as tar:
        assert tar.getnames() == ["textures_etc/units/pig/pig_1.webp"]
        assert all(m.mtime == 0 and m.uid == 0 and not m.uname for m in tar.getmembers())


def test_fetch_restores_the_same_files(dist, tmp_path):
    out = tmp_path / "fetched"
    fetch_assets.fetch(dist.as_uri() + "/", out, list(fetch_assets.ARCHIVES))
    for rel, data in FILES.items():
        assert (out / rel).read_bytes() == data
    assert json.loads((out / "manifest.json").read_text())["parts"]["json"]["files"] == 4


def test_fetch_only_json(dist, tmp_path):
    out = tmp_path / "fetched"
    fetch_assets.fetch(dist.as_uri() + "/", out, ["json"])
    assert (out / "ui/1024x768/popup.json").exists()
    assert not (out / "textures_etc/units/pig/pig_1.webp").exists()


def test_fetch_rejects_damaged_archive(dist, tmp_path):
    with (dist / fetch_assets.ARCHIVES["json"]).open("ab") as f:
        f.write(b"garbage")
    with pytest.raises(SystemExit, match="sha256"):
        fetch_assets.fetch(dist.as_uri() + "/", tmp_path / "fetched", ["json"])


def test_fetch_cli_with_base_url(dist, tmp_path, capsys):
    assert fetch_assets.main(["--base-url", dist.as_uri(), "--only", "json",
                              "--out", str(tmp_path / "fetched")]) == 0
    assert "mobi.rjg.underfire 1.3.12" in capsys.readouterr().out


def test_copy_fonts_patch_overrides_main(tmp_path):
    raw = tmp_path / "raw"
    for layer, name, data in (("obb_main", "Play.ttf", b"old"), ("obb_patch", "Play.ttf", b"new"),
                              ("apk", "Other.ttf", b"x")):
        (raw / layer / "assets/fonts").mkdir(parents=True, exist_ok=True)
        (raw / layer / "assets/fonts" / name).write_bytes(data)
    out = tmp_path / "assets"
    assert build_assets.copy_fonts(raw, out) == 2
    assert (out / "fonts/Play.ttf").read_bytes() == b"new"
