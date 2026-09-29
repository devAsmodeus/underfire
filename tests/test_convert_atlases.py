"""Атласы Inferno → JSON PixiJS 8 на синтетических данных; файлы игры не нужны."""
import json

import convert_atlases as ca
import pytest
from PIL import Image

UX = [1, 1, 0, -1, -1, -1, 0, 1]      # groupD8.uX / uY из PixiJS 8 для поворотов 0…7
UY = [0, 1, 1, 1, 0, -1, -1, -1]


def pixi_render(entry: dict, page: Image.Image) -> Image.Image:
    """Как PixiJS 8.21 рисует кадр с anchor (0, 0): Spritesheet._processFrames (прямоугольник на
    странице у rotated — (x, y, h, w), rotate = 2), Texture.updateUvs (углы через groupD8),
    updateQuadBounds (четырёхугольник — trim внутри orig). Выборка — ближайший тексель."""
    fr, rotate = entry["frame"], 2 if entry["rotated"] else 0
    x, y, w, h = fr["x"], fr["y"], fr["w"], fr["h"]
    fw, fh = (h, w) if rotate else (w, h)
    trimmed = entry["trimmed"]
    orig = entry["sourceSize"] if trimmed else {"w": w, "h": h}
    tx, ty = (entry["spriteSourceSize"]["x"], entry["spriteSourceSize"]["y"]) if trimmed else (0, 0)
    if rotate:
        cx, cy, w2, h2 = x + fw / 2, y + fh / 2, fw / 2, fh / 2
        r, corners = (rotate + 5) % 8, []           # groupD8.add(rotate, NW), дальше +2
        for _ in range(4):
            corners.append((cx + w2 * UX[r], cy + h2 * UY[r]))
            r = (r + 2) % 8
    else:
        corners = [(x, y), (x + fw, y), (x + fw, y + fh), (x, y + fh)]
    (x0, y0), (x1, y1), _, (x3, y3) = corners       # вершины: TL, TR, BR, BL
    out = Image.new("RGBA", (orig["w"], orig["h"]))
    for py in range(h):
        for px in range(w):
            u, v = (px + 0.5) / w, (py + 0.5) / h
            sx, sy = x0 + (x1 - x0) * u + (x3 - x0) * v, y0 + (y1 - y0) * u + (y3 - y0) * v
            out.putpixel((tx + px, ty + py), page.getpixel((int(sx), int(sy))))
    return out


def sprite(w: int, h: int) -> Image.Image:
    """Картинка с уникальным цветом каждого пикселя."""
    img = Image.new("RGBA", (w, h))
    img.putdata([(10 + i, 200 - i, i * 3 % 256, 255) for i in range(w * h)])
    return img


def pack(page: Image.Image, img: Image.Image, at: tuple[int, int], offset: tuple[int, int],
         source: tuple[int, int], rotated: bool) -> ca.Frame:
    """Уложить обрезанный кадр на страницу так, как это делает упаковщик Inferno: повёрнутый —
    на 90° по часовой, и поля w,h и ox,oy тогда тоже в повёрнутом виде."""
    stored = img.transpose(Image.Transpose.ROTATE_270) if rotated else img   # ROTATE_270 — по часовой
    page.paste(stored, at)
    (ox, oy), (w, h) = (offset[::-1], stored.size) if rotated else (offset, img.size)
    return ca.Frame("f.png", *at, w, h, ox, oy, *source, rotated)


def placed(img: Image.Image, offset: tuple[int, int], source: tuple[int, int]) -> Image.Image:
    out = Image.new("RGBA", source)
    out.paste(img, offset)
    return out


ATLAS = ("textures: pig_1.png\r\n"
         "/pig_e_1.png\t0\t0\t5\t3\t2\t1\t9\t8\t\r\n"
         "/pig_e_3.png\t5\t0\t180\t146\t7\t54\t272\t241\tr\r\n"
         "\r\n")


def test_parse_atlas():
    page, frames = ca.parse_atlas(ATLAS)
    assert page == "pig_1.png"
    assert frames == [ca.Frame("pig_e_1.png", 0, 0, 5, 3, 2, 1, 9, 8),
                      ca.Frame("pig_e_3.png", 5, 0, 180, 146, 7, 54, 272, 241, True)]
    # cells.atlas: другой заголовок, имена без «/», концы строк LF
    page, frames = ca.parse_atlas("textures: atlas.png\nborder.png\t61\t0\t46\t32\t0\t0\t46\t32\t\n")
    assert (page, frames[0].name) == ("atlas.png", "border.png")


@pytest.mark.parametrize("text, error", [
    ("/a.png\t0\t0\t1\t1\t0\t0\t1\t1\n", "заголовка"),
    ("textures: a.png\n/a.png\t0\t0\t1\t1\t0\t0\t1\n", "9 полей"),
    ("textures: a.png\n/a.png\t0\t0\t1\t1\t0\t0\t1\t1\tx\n", "9 полей"),
    ("textures: a.png\n/a.png\t0\t0\tw\t1\t0\t0\t1\t1\n", "не число"),
])
def test_parse_atlas_rejects_broken_lines(text, error):
    with pytest.raises(ValueError, match=error):
        ca.parse_atlas(text)


def test_frame_fields():
    _, (plain, rotated) = ca.parse_atlas(ATLAS)
    assert ca.pixi_frame(plain, 1024, 1024) == ({
        "frame": {"x": 0, "y": 0, "w": 5, "h": 3}, "rotated": False, "trimmed": True,
        "spriteSourceSize": {"x": 2, "y": 1, "w": 5, "h": 3}, "sourceSize": {"w": 9, "h": 8},
    }, False)
    # research_center_3_e_45: w=180 h=146 ox=7 oy=54 r — сосед e_43 без поворота: 146×180 в (54, 7)
    assert ca.pixi_frame(rotated, 1024, 1024) == ({
        "frame": {"x": 5, "y": 0, "w": 146, "h": 180}, "rotated": True, "trimmed": True,
        "spriteSourceSize": {"x": 54, "y": 7, "w": 146, "h": 180}, "sourceSize": {"w": 272, "h": 241},
    }, False)
    untrimmed = ca.Frame("u.png", 2, 2, 121, 118, 0, 0, 121, 118)
    assert ca.pixi_frame(untrimmed, 256, 256)[0]["trimmed"] is False


@pytest.mark.parametrize("rotated", [False, True])
def test_pixi_shows_packed_frame_upright(rotated):
    page = Image.new("RGBA", (16, 16))
    img = sprite(5, 3)
    frame = pack(page, img, at=(4, 6), offset=(2, 1), source=(9, 8), rotated=rotated)
    entry, clipped = ca.pixi_frame(frame, *page.size)
    assert not clipped
    assert pixi_render(entry, page).tobytes() == placed(img, (2, 1), (9, 8)).tobytes()


def test_frame_beyond_page_is_clipped():
    # tutorial_menu: x=2, w=2048 на странице шириной 2048 — два правых столбца за краем
    page = Image.new("RGBA", (8, 8))
    img = sprite(5, 3)
    frame = pack(page, img, at=(5, 1), offset=(0, 2), source=(5, 5), rotated=False)
    entry, clipped = ca.pixi_frame(frame, *page.size)
    assert clipped and entry["frame"]["w"] == 3 and entry["sourceSize"] == {"w": 5, "h": 5}
    expected = placed(img.crop((0, 0, 3, 3)), (0, 2), (5, 5))       # срезанное — прозрачно
    assert pixi_render(entry, page).tobytes() == expected.tobytes()


def test_rotated_frame_beyond_page_is_clipped():
    # Повёрнутый кадр 4×6 лежит на странице как 6×4; за правый край уходят 2 столбца страницы
    # (это верхние строки кадра), за нижний — 1 строка (правый столбец кадра).
    page = Image.new("RGBA", (10, 7))
    img = sprite(4, 6)
    big = Image.new("RGBA", (12, 8))
    frame = pack(big, img, at=(6, 4), offset=(1, 2), source=(7, 9), rotated=True)
    page.paste(big.crop((0, 0, 10, 7)), (0, 0))
    entry, clipped = ca.pixi_frame(frame, *page.size)
    assert clipped
    assert entry["spriteSourceSize"] == {"x": 1, "y": 4, "w": 3, "h": 4}
    expected = placed(img.crop((0, 2, 3, 6)), (1, 4), (7, 9))
    assert pixi_render(entry, page).tobytes() == expected.tobytes()


def test_empty_frame_is_kept():
    entry, _ = ca.pixi_frame(ca.Frame("e.png", 0, 0, 0, 0, 457, 370, 457, 370), 64, 64)
    assert entry["frame"] == {"x": 0, "y": 0, "w": 0, "h": 0} and entry["trimmed"] is True


def test_duplicate_frame_in_one_atlas_is_an_error():
    f = ca.Frame("a.png", 0, 0, 1, 1, 0, 0, 1, 1)
    with pytest.raises(ValueError, match="дважды"):
        ca.sheet([f, f], "a.webp", (4, 4))


def test_page_set_follows_engine_rule():
    stems = {"b/e", "b/e_1", "b/e_2", "b/w", "u/pig_1", "u/pig_2", "g/x", "g/x_1", "g/x_3"}
    assert ca.page_set("b/e", stems, set()) == ["b/e_1", "b/e_2"]       # X из main → страницы
    assert ca.page_set("b/e", stems, {"b/e"}) == ["b/e"]                 # X из patch → X
    assert ca.page_set("b/w", stems, set()) == ["b/w"]
    assert ca.page_set("u/pig", stems, set()) == ["u/pig_1", "u/pig_2"]
    assert ca.page_set("g/x", stems, set()) == ["g/x_1"]                 # до первого пропуска
    assert ca.page_set("nope", stems, set()) == []
    assert ca.shadowed(stems, set()) == {"b/e", "g/x", "g/x_3"}
    assert ca.shadowed(stems, {"b/e"}) == {"b/e_1", "b/e_2", "g/x", "g/x_3"}


def test_indexes_split_hd_sd_and_skip_shadowed():
    def one(*names, w=1):
        return {"frames": {n: {"frame": {"x": 0, "y": 0, "w": w, "h": 1}, "rotated": False,
                               "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": 1},
                               "sourceSize": {"w": w, "h": 1}} for n in names}}
    sheets = {
        "textures_etc/interface/1024x768/city/menu.json": one("ok.png", "hd_only.png", w=2),
        "textures_etc/interface/1024x768_sd/city/menu.json": one("ok.png", "sd_only.png"),
        "textures_etc/mobs/bug/bug_1.json": one("bug_e_1.png", w=5),
        "textures_etc/citizens/bug/bug_1.json": one("bug_e_1.png", w=3),
        "textures_etc/buildings/b/e/e.json": one("b_e_0.png", "old.png"),
        "textures_etc/buildings/b/e/e_1.json": one("b_e_0.png"),
    }
    index, index_sd, stats = ca.build_indexes(sheets, hidden={"textures_etc/buildings/b/e/e"})
    assert index == {
        "ok.png": "textures_etc/interface/1024x768/city/menu.json",
        "hd_only.png": "textures_etc/interface/1024x768/city/menu.json",
        "sd_only.png": "textures_etc/interface/1024x768_sd/city/menu.json",   # только в SD
        "bug_e_1.png": "textures_etc/citizens/bug/bug_1.json",                # первый по пути
        "b_e_0.png": "textures_etc/buildings/b/e/e_1.json",                   # e.json не грузится
    }
    assert index_sd == {"ok.png": "textures_etc/interface/1024x768_sd/city/menu.json"}
    assert stats == {"ambiguous": 1, "ambiguous_same": 0}


def put(raw, layer, rel, data):
    path = raw / layer / "assets" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


@pytest.fixture
def raw(tmp_path, make_ccz):
    raw = tmp_path / "raw"
    t = "textures_etc/"
    put(raw, "obb_main", t + "units/pig/pig_1.atlas", ATLAS)
    put(raw, "obb_main", t + "units/pig/pig_1.pkm.ccz", make_ccz(1024, 1024, 1024, 512))
    put(raw, "obb_main", t + "maps/city/cells.atlas",
        "textures: atlas.png\nborder.png\t0\t0\t46\t32\t0\t0\t46\t32\t\n")
    put(raw, "obb_main", t + "maps/city/cells.pkm.ccz", make_ccz(128, 128, 128, 64))
    put(raw, "obb_main", t + "effects/tracers/tracers.atlas",
        "textures: tracers.png          \r\n/tracers_s_idle_4.png\t0\t0\t42\t5\t0\t1\t43\t7\t\r\n")
    tracers = tmp_path / "tracers.png"
    Image.new("RGBA", (64, 32)).save(tracers)
    put(raw, "obb_main", t + "effects/tracers/tracers.png", tracers.read_bytes())
    ui = "textures: menu.png\n/ok.png\t2\t2\t{0}\t{0}\t0\t0\t{0}\t{0}\t\n/wide.png\t2\t10\t64\t4\t0\t0\t64\t4\t\n"
    put(raw, "obb_main", t + "interface/1024x768/city/menu.atlas", ui.format(20))
    put(raw, "obb_main", t + "interface/1024x768/city/menu.pkm.ccz", make_ccz(64, 64, 64, 32))
    put(raw, "obb_patch", t + "interface/1024x768_sd/city/menu.atlas", ui.format(10))
    put(raw, "obb_patch", t + "interface/1024x768_sd/city/menu.pkm.ccz", make_ccz(32, 32, 32, 16))
    for stem in ("e", "e_1"):                   # старый e.atlas и страницы e_1 — движок берёт e_1
        put(raw, "obb_main", t + f"buildings/b/e/{stem}.atlas",
            f"textures: {stem}.png\n/b_e_0.png\t0\t0\t4\t4\t0\t0\t4\t4\t\n")
        put(raw, "obb_main", t + f"buildings/b/e/{stem}.pkm.ccz", make_ccz(16, 16, 16, 8))
    return raw


def test_convert_all(raw, tmp_path):
    out = tmp_path / "assets"
    s = ca.convert_all(raw, out)
    assert (s.atlases, s.frames, s.rotated, s.empty, s.errors) == (7, 10, 1, 0, {})
    assert s.header_mismatch == ["textures_etc/maps/city/cells.atlas: atlas.png"]
    assert s.plain_pages == ["textures_etc/effects/tracers/tracers.atlas: tracers.png"]
    assert s.clipped == ["textures_etc/interface/1024x768/city/menu.atlas: wide.png",   # как
                         "textures_etc/interface/1024x768_sd/city/menu.atlas: wide.png"]  # tutorial_menu
    assert s.hidden == ["textures_etc/buildings/b/e/e.atlas"]

    def load(rel):
        return json.loads((out / rel).read_text())
    pig = load("textures_etc/units/pig/pig_1.json")
    assert pig["meta"] == {"image": "pig_1.webp", "size": {"w": 1024, "h": 512}, "scale": "1"}
    assert list(pig["frames"]) == ["pig_e_1.png", "pig_e_3.png"]
    cells = load("textures_etc/maps/city/cells.json")          # страница — по имени файла атласа
    assert cells["meta"]["image"] == "cells.webp" and "border.png" in cells["frames"]
    tracers = load("textures_etc/effects/tracers/tracers.json")
    assert tracers["meta"] == {"image": "tracers.png", "size": {"w": 64, "h": 32}, "scale": "1"}
    assert (out / "textures_etc/effects/tracers/tracers.png").is_file()
    assert load("frames_index.json") == {
        "b_e_0.png": "textures_etc/buildings/b/e/e_1.json",
        "border.png": "textures_etc/maps/city/cells.json",
        "ok.png": "textures_etc/interface/1024x768/city/menu.json",
        "pig_e_1.png": "textures_etc/units/pig/pig_1.json",
        "pig_e_3.png": "textures_etc/units/pig/pig_1.json",
        "tracers_s_idle_4.png": "textures_etc/effects/tracers/tracers.json",
        "wide.png": "textures_etc/interface/1024x768/city/menu.json",
    }
    assert load("frames_index_sd.json") == {
        "ok.png": "textures_etc/interface/1024x768_sd/city/menu.json",
        "wide.png": "textures_etc/interface/1024x768_sd/city/menu.json",
    }


def test_cli_reports_and_fails_on_broken_atlas(raw, tmp_path, capsys):
    assert ca.main(["--raw", str(raw), "--out", str(tmp_path / "a")]) == 0
    assert "атласов: 7, кадров: 10 (повёрнутых 1" in capsys.readouterr().out
    put(raw, "obb_patch", "textures_etc/units/pig/pig_2.atlas", "textures: pig_2.png\n/x\t1\n")
    assert ca.main(["--raw", str(raw), "--out", str(tmp_path / "b")]) == 1
    assert "pig_2.atlas" in capsys.readouterr().err
