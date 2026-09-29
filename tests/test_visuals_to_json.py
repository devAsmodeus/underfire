"""Визуалы config/visuals → JSON на синтетических XML и атласах; файлы игры не нужны."""
import json

import convert_atlases
import pytest
import visuals_to_json as vj

UNIT = """<?xml version="1.0" encoding="utf-8"?>
<visual xmlns:xsd="http://www.w3.org/2001/XMLSchema" name="bug" fps="15" scale="0.5" atlases="bug,">
  <directions>
    <direction name="e" prefix="e" atlases="" offsetX="-64" offsetY="-82" width="128" height="125">
      <states>
        <state name="run"><layers><layer frameCount="3" frames="1,3,5," /></layers></state>
        <state name="die_1"><layers><layer frameCount="2" frames="7,9," /></layers></state>
      </states>
    </direction>
    <direction name="n" prefix="e" atlases="" offsetX="-66" offsetY="-82" width="128" height="125">
      <states>
        <state name="run"><layers><layer frameCount="3" frames="1,3,5," /></layers></state>
      </states>
    </direction>
  </directions>
</visual>"""

BUILDING = """<?xml version="1.0" encoding="utf-8"?>
<visual name="gun_1" fps="15" scale="1" atlases="">
  <directions>
    <direction name="w" prefix="w" atlases="w," offsetX="0" offsetY="-71" width="96" height="89"
               hitArea="0,0,60,40,60,40,120,0,120,0,0,0">
      <states>
        <state name="idle"><layers>
          <layer frameCount="1" frames="0," />
          <layer frameCount="4" frames="2,4," />
        </layers></state>
      </states>
    </direction>
  </directions>
</visual>"""


def test_parse_visual():
    v = vj.parse_visual(UNIT)
    assert (v["name"], v["fps"], v["scale"], v["atlases"]) == ("bug", 15, 0.5, ["bug"])
    assert list(v["directions"]) == ["e", "n"]
    e, n = v["directions"]["e"], v["directions"]["n"]
    assert e == {"prefix": "e", "mirror": False, "offsetX": -64, "offsetY": -82, "width": 128,
                 "height": 125, "atlases": [],
                 "states": {"run": [{"frameCount": 3, "frames": [1, 3, 5]}],
                            "die_1": [{"frameCount": 2, "frames": [7, 9]}]}}
    assert (n["prefix"], n["mirror"], n["offsetX"]) == ("e", True, -66)   # n рисуется отражённым e
    b = vj.parse_visual(BUILDING)["directions"]["w"]
    assert b["hitArea"] == [0, 0, 60, 40, 60, 40, 120, 0, 120, 0, 0, 0]
    assert b["states"]["idle"] == [{"frameCount": 1, "frames": [0]},       # слои — снизу вверх;
                                   {"frameCount": 4, "frames": [2, 4]}]     # frameCount как в XML


def test_defaults_and_empty_hit_area():
    v = vj.parse_visual('<visual name="x"><directions><direction name="w" prefix="w" hitArea="">'
                        "</direction></directions></visual>")
    assert (v["fps"], v["scale"], v["atlases"]) == (30, 1.0, [])            # умолчания движка
    assert "hitArea" not in v["directions"]["w"] and v["directions"]["w"]["states"] == {}


@pytest.mark.parametrize("xml, error", [
    ("<visuals/>", "ожидался <visual>"),
    ('<visual name="x"><directions><direction name="w" prefix="w"><states><state name="s"><layers>'
     '<layer frameCount="1" frames="1,a," /></layers></state></states></direction></directions>'
     "</visual>", "не число"),
])
def test_parse_visual_rejects(xml, error):
    with pytest.raises(ValueError, match=error):
        vj.parse_visual(xml)


def test_frame_name():
    assert vj.frame_name("bomb_pig", "e", 27) == "bomb_pig_e_27.png"


def test_resolve_atlases_follows_engine_paths():
    stems = {"textures_etc/mobs/bug/bug_1", "textures_etc/mobs/bug/bug_2",
             "textures_etc/buildings/gun_1/w/w", "textures_etc/buildings/gun_1/w/w_1"}
    unit, missing = vj.resolve_atlases(vj.parse_visual(UNIT), "mobs", stems, set())
    assert unit["atlases"] == ["textures_etc/mobs/bug/bug_1.json", "textures_etc/mobs/bug/bug_2.json"]
    assert missing == []
    # здание: атласы направления лежат в buildings/<name>/<prefix>/; w при страницах w_1 не грузится
    building, missing = vj.resolve_atlases(vj.parse_visual(BUILDING), "territories", stems, set())
    assert building["directions"]["w"]["atlases"] == ["textures_etc/buildings/gun_1/w/w_1.json"]
    _, missing = vj.resolve_atlases(vj.parse_visual(UNIT), "citizens", stems, set())
    assert missing == ["textures_etc/citizens/bug/bug"]


def put(raw, layer, rel, data):
    path = raw / layer / "assets" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())


def atlas(page, *names):
    return f"textures: {page}.png\n" + "".join(f"/{n}\t0\t0\t2\t2\t0\t0\t2\t2\t\n" for n in names)


@pytest.fixture
def assets(tmp_path, make_ccz):
    """raw/ с двумя одноимёнными визуалами разных категорий (как mobs/bug и citizens/bug), зданием
    и эффектом без текстур; атласы и индекс собирает convert_atlases."""
    raw, out = tmp_path / "raw", tmp_path / "assets"
    t = "textures_etc/"
    for cat, frames in (("mobs", [f"bug_e_{n}.png" for n in (1, 3, 5, 7, 9)]),
                        ("citizens", [f"bug_e_{n}.png" for n in (1, 3, 5)])):
        put(raw, "obb_main", f"{t}{cat}/bug/bug_1.atlas", atlas("bug_1", *frames))
        put(raw, "obb_main", f"{t}{cat}/bug/bug_1.pkm.ccz", make_ccz(8, 8, 8, 4))
        put(raw, "obb_main", f"config/visuals/{cat}/bug.xml", UNIT)
    put(raw, "obb_patch", t + "buildings/gun_1/w/w_1.atlas", atlas("w_1", "gun_1_w_0.png", "gun_1_w_2.png"))
    put(raw, "obb_patch", t + "buildings/gun_1/w/w_1.pkm.ccz", make_ccz(8, 8, 8, 4))
    put(raw, "obb_patch", "config/visuals/buildings/gun_1.xml", BUILDING)
    put(raw, "apk", "config/visuals/effects/ghost.xml", UNIT.replace('name="bug"', 'name="ghost"'))
    convert_atlases.convert_all(raw, out)
    return raw, out


def test_convert_all(assets):
    raw, out = assets
    s = vj.convert_all(raw, out)
    assert (s.visuals, s.directions, s.errors) == (4, 7, {})
    assert s.mirrored == {"n→e": 3}
    mob = json.loads((out / "visuals/mobs/bug.json").read_text())
    assert mob["atlases"] == ["textures_etc/mobs/bug/bug_1.json"]
    citizen = json.loads((out / "visuals/citizens/bug.json").read_text())
    assert citizen["atlases"] == ["textures_etc/citizens/bug/bug_1.json"]
    gun = json.loads((out / "visuals/buildings/gun_1.json").read_text())
    assert gun["directions"]["w"]["atlases"] == ["textures_etc/buildings/gun_1/w/w_1.json"]
    assert gun["directions"]["w"]["hitArea"][:4] == [0, 0, 60, 40]
    # кадры: у bug — e_1…e_9 (n берёт кадры e); у ghost нет ни одного, у gun_1 нет кадра 4.
    # У citizens/bug нет e_7 и e_9 в своих атласах, но индекс находит их у mobs/bug — чужая графика.
    assert s.frames == 5 + 5 + 5 + 3
    assert s.visuals_missing == {"effects/ghost": 5, "buildings/gun_1": 1}
    assert (s.not_in_index, s.not_in_own) == (6, 8)
    # индекс ведёт bug_e_1…e_5 в citizens (первый по пути), а у mobs/bug свои атласы — это видно
    assert s.visuals_elsewhere == {"mobs/bug": 3}
    assert s.unresolved == ["effects/ghost: textures_etc/effects/ghost/bug"]


def test_cli(assets, capsys):
    raw, out = assets
    assert vj.main(["--raw", str(raw), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "визуалов: 4, направлений: 7 (отражённых: n→e 3)" in printed
    assert "нет в frames_index.json: 6 (2 визуалов)" in printed
    with pytest.raises(SystemExit, match="convert_atlases"):
        vj.main(["--raw", str(raw), "--out", str(out / "nowhere")])
