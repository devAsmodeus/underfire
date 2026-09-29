"""Декодер *.pkm.ccz на синтетических текстурах: ETC1 подменяется фейковым декодером."""
import os
import struct
import zlib

import decode_textures as dt
import pytest
from PIL import Image


def fake_decoder(pixel):
    """Вместо ETC1: pixel(x, y, payload) → (r, g, b), ответ в BGRA, как у texture2ddecoder."""
    def decode(payload, width, height):
        out = bytearray()
        for y in range(height):
            for x in range(width):
                r, g, b = pixel(x, y, payload)
                out += bytes((b, g, r, 255))
        return bytes(out)
    return decode


def masked(x, y, payload):
    """Сверху (y < 4) цвет, снизу маска в R; G и B снизу нарочно другие — альфа берётся из R.
    Первый байт данных = 1 — маска целиком 255."""
    if y < 4:
        return x * 30, y * 40, 5
    alpha = 255 if payload[:1] == b"\x01" else (x + (y - 4) * 6) * 10
    return alpha, 7, 9


def test_alpha_from_red_channel_of_bottom_half(make_ccz):
    pkm = dt.parse_pkm(dt.read_ccz(make_ccz(8, 8, 6, 4)))        # 8×8 закодировано, 6×4 исходно
    img = dt.to_image(pkm, fake_decoder(masked))
    assert (img.mode, img.size) == ("RGBA", (6, 4))              # обрезано по ширине и высоте
    for y in range(4):
        for x in range(6):
            assert img.getpixel((x, y)) == (x * 30, y * 40, 5, (x + y * 6) * 10)


def test_mask_of_255_is_dropped(make_ccz):
    payload = b"\x01" + bytes(31)
    img = dt.to_image(dt.parse_pkm(dt.read_ccz(make_ccz(8, 8, 6, 4, payload))),
                      fake_decoder(masked))
    assert (img.mode, img.size) == ("RGB", (6, 4))
    assert img.getpixel((5, 3)) == (150, 120, 5)


def test_texture_without_mask_is_cropped(make_ccz):
    # Высота не удвоена (иконка 455×279 в 456×280): просто обрезка, альфы нет.
    img = dt.to_image(dt.parse_pkm(dt.read_ccz(make_ccz(8, 8, 7, 5))),
                      fake_decoder(lambda x, y, _: (x, y, 1)))
    assert (img.mode, img.size) == ("RGB", (7, 5))
    assert img.getpixel((6, 4)) == (6, 4, 1)


def test_ccz_is_validated():
    pkm = b"PKM 10" + bytes(10)
    with pytest.raises(ValueError, match="не CCZ"):
        dt.read_ccz(b"XXXX" + bytes(12))
    with pytest.raises(ValueError, match="тип сжатия"):
        dt.read_ccz(b"CCZ!" + struct.pack(">HHII", 1, 2, 0, len(pkm)) + zlib.compress(pkm))
    with pytest.raises(ValueError, match="в заголовке"):
        dt.read_ccz(b"CCZ!" + struct.pack(">HHII", 0, 2, 0, 99) + zlib.compress(pkm))


def test_pkm_is_validated(make_ccz):
    with pytest.raises(ValueError, match="не PKM"):
        dt.parse_pkm(b"PKM 20" + bytes(100))
    with pytest.raises(ValueError, match="формат"):
        dt.parse_pkm(dt.read_ccz(make_ccz(8, 8, 8, 4, fmt=1)))
    with pytest.raises(ValueError, match="не помещается"):
        dt.parse_pkm(dt.read_ccz(make_ccz(8, 8, 9, 4)))
    with pytest.raises(ValueError, match="нужно"):
        dt.parse_pkm(dt.read_ccz(make_ccz(8, 8, 8, 4, payload=bytes(10))))


def test_pkm_size_reads_only_header(tmp_path, make_ccz):
    big = tmp_path / "big.pkm.ccz"                   # несжимаемые данные: заголовок в первом блоке
    big.write_bytes(make_ccz(512, 512, 500, 256, payload=os.urandom(512 * 512 // 2)))
    assert dt.pkm_size(big) == (500, 256)
    (tmp_path / "bad.pkm.ccz").write_bytes(b"nope" + bytes(40))
    with pytest.raises(ValueError, match="не CCZ"):
        dt.pkm_size(tmp_path / "bad.pkm.ccz")


def put(raw, layer, rel, data):
    path = raw / layer / "assets" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_layers_patch_over_main_over_apk(tmp_path):
    raw = tmp_path / "raw"
    put(raw, "apk", "t/a.pkm.ccz", b"apk")
    put(raw, "obb_main", "t/a.pkm.ccz", b"main")
    put(raw, "obb_main", "t/b.pkm.ccz", b"main")
    put(raw, "obb_patch", "t/b.pkm.ccz", b"patch")
    put(raw, "obb_patch", "t/c.pkm.ccz", b"patch")
    put(raw, "obb_patch", "t/.DS_Store", b"")
    files = dt.layered_files(raw, ".pkm.ccz")
    assert {rel: p.read_bytes() for rel, p in files.items()} == {
        "t/a.pkm.ccz": b"main", "t/b.pkm.ccz": b"patch", "t/c.pkm.ccz": b"patch"}
    assert [dt.layer_of(raw, p) for p in files.values()] == ["obb_main", "obb_patch", "obb_patch"]


@pytest.fixture
def raw(tmp_path, make_ccz):
    raw = tmp_path / "raw"
    put(raw, "obb_main", "textures_etc/units/pig/pig_1.pkm.ccz", make_ccz(8, 8, 6, 4))
    put(raw, "obb_main", "textures_etc/maps/tile.pkm.ccz",
        make_ccz(8, 8, 8, 4, payload=b"\x01" + bytes(31)))            # маска 255 → RGB
    put(raw, "obb_patch", "textures_etc/icons/base.pkm.ccz", make_ccz(8, 8, 7, 5))
    return raw


def test_decode_all_writes_webp(raw, tmp_path):
    out = tmp_path / "assets"
    s = dt.decode_all(raw, out, decode=fake_decoder(masked))
    assert (s.selected, s.written, s.skipped, s.rgba, s.rgb, s.errors) == (3, 3, 0, 1, 2, {})
    got = {p.relative_to(out).as_posix(): Image.open(p) for p in out.rglob("*") if p.is_file()}
    assert {rel: (im.format, im.mode, im.size) for rel, im in got.items()} == {
        "textures_etc/units/pig/pig_1.webp": ("WEBP", "RGBA", (6, 4)),
        "textures_etc/maps/tile.webp": ("WEBP", "RGB", (8, 4)),
        "textures_etc/icons/base.webp": ("WEBP", "RGB", (7, 5)),
    }
    alpha = got["textures_etc/units/pig/pig_1.webp"].getchannel("A")
    assert alpha.tobytes() == bytes(i * 10 for i in range(24))    # альфа — без потерь
    assert s.bytes == sum(p.stat().st_size for p in out.rglob("*.webp"))


def test_up_to_date_files_are_skipped(raw, tmp_path):
    out, decode = tmp_path / "assets", fake_decoder(masked)
    dt.decode_all(raw, out, decode=decode)
    again = dt.decode_all(raw, out, decode=decode)
    assert (again.written, again.skipped) == (0, 3)
    src = raw / "obb_main/assets/textures_etc/maps/tile.pkm.ccz"   # исходник новее результата
    later = (out / "textures_etc/maps/tile.webp").stat().st_mtime + 10
    os.utime(src, (later, later))
    assert dt.decode_all(raw, out, decode=decode).written == 1
    assert dt.decode_all(raw, out, force=True, decode=decode).written == 3


def test_only_filters_by_path(raw, tmp_path):
    out = tmp_path / "assets"
    s = dt.decode_all(raw, out, only=["textures_etc/units/*", "*/tile.*"],
                      decode=fake_decoder(masked))
    assert s.selected == s.written == 2
    assert sorted(p.name for p in out.rglob("*.webp")) == ["pig_1.webp", "tile.webp"]


def test_cli_with_real_decoder(raw, tmp_path, capsys):
    # Настоящий texture2ddecoder на нулевых блоках и пул процессов; битая текстура — код 1.
    put(raw, "obb_patch", "textures_etc/bad.pkm.ccz", b"CCZ!" + bytes(12) + b"garbage")
    code = dt.main(["--raw", str(raw), "--out", str(tmp_path / "assets"), "--jobs", "2"])
    captured = capsys.readouterr()
    assert code == 1
    assert "текстур: 4, записано 3" in captured.out and "ошибок 1" in captured.out
    assert "textures_etc/bad.pkm.ccz" in captured.err
    assert Image.open(tmp_path / "assets/textures_etc/units/pig/pig_1.webp").size == (6, 4)
