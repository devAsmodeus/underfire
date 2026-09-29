"""Распаковка XAPK на игрушечном архиве той же структуры, что у настоящего."""
import io
import json
import zipfile

import extract_xapk
import pytest


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def xapk(tmp_path):
    apk = _zip({"assets/config/a.xml": b"<a/>", "assets/sounds/b.wav": b"RIFF",
                "lib/armeabi/libinferno.so": b"\x7fELF", "classes.dex": b"dex"})
    main = _zip({"assets/textures_etc/t.pkm.ccz": b"CCZ!", "assets/.DS_Store": b""})
    patch = _zip({"assets/config/config.xml": b"<x/>"})
    obb = "Android/obb/mobi.rjg.underfire/"
    path = tmp_path / "game.xapk"
    path.write_bytes(_zip({
        "mobi.rjg.underfire.apk": apk,
        f"{obb}main.13.mobi.rjg.underfire.obb": main,
        f"{obb}patch.59.mobi.rjg.underfire.obb": patch,
        "manifest.json": json.dumps({"package_name": "mobi.rjg.underfire",
                                     "version_name": "1.3.12"}).encode(),
        "icon.png": b"png",
    }))
    return path


def test_layout(xapk, tmp_path):
    out = tmp_path / "raw"
    assert extract_xapk.extract(xapk, out) == {"apk": 2, "obb_main": 2, "obb_patch": 1}
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files == [                                   # из APK — только assets/, без кода
        "apk/assets/config/a.xml", "apk/assets/sounds/b.wav",
        "obb_main/assets/.DS_Store", "obb_main/assets/textures_etc/t.pkm.ccz",
        "obb_patch/assets/config/config.xml",
    ]


def test_refuses_to_overwrite_without_force(xapk, tmp_path):
    out = tmp_path / "raw"
    extract_xapk.extract(xapk, out)
    with pytest.raises(SystemExit):
        extract_xapk.extract(xapk, out)
    (out / "apk" / "stale.txt").write_text("old")
    extract_xapk.extract(xapk, out, force=True)
    assert not (out / "apk" / "stale.txt").exists()


def test_rejects_unexpected_archive(tmp_path):
    path = tmp_path / "other.xapk"
    path.write_bytes(_zip({"other.apk": _zip({"assets/x": b"x"})}))
    with pytest.raises(SystemExit):
        extract_xapk.extract(path, tmp_path / "raw")
    assert not (tmp_path / "raw").exists()


def test_cli_reports_counts(xapk, tmp_path, capsys):
    extract_xapk.main([str(xapk), "--out", str(tmp_path / "raw")])
    printed = capsys.readouterr().out
    assert "apk: файлов 2" in printed and "ожидалось 160" in printed
