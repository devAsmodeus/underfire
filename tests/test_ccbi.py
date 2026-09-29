"""Макеты .ccbi без файлов игры: синтетический макет → .ccbi → разбор → тот же JSON, плюс байты,
собранные вручную по спецификации (чтобы разбор и писатель не могли ошибиться согласованно)."""
import json
import struct

import ccbi_to_json as ccbi
import ccbi_write
import pytest


def node(base, *children, custom=None, member=None, props=None, custom_props=None, animated=None):
    return {"baseClass": base, "customClass": custom, "memberVarAssignment": member,
            "properties": props or {}, "customProperties": custom_props or {},
            "animatedProperties": animated or {}, "children": list(children)}


def prop(ptype, value, **extra):
    return {"type": ptype, "value": value, **extra}


def kf(time, value, easing="Linear", **opt):
    return {"time": time, "easing": easing, **opt, "value": value}


BLOCK_SOUND = {"selector": "close", "target": "Owner", "soundFile": "click.wav",
               "soundEnabled": True}

# Синтетический макет: все 29 типов свойств, все 8 анимируемых типов, свой класс поверх плагина,
# платформенные свойства, таймлайны с колбэками и звуками, float32 без точного десятичного вида.
LAYOUT = {
    "sequences": [
        {"sequenceId": 0, "name": "Default Timeline", "duration": 10, "chainedSequenceId": -1,
         "callbacks": [], "sounds": []},
        {"sequenceId": 1, "name": "timelineShow", "duration": 0.5, "chainedSequenceId": 0,
         "callbacks": [{"time": 0.5, "selector": "onShown", "target": "Owner"}],
         "sounds": [{"time": 0, "file": "open.wav", "pitch": 1, "pan": -0.25, "gain": 0.8}]},
    ],
    "autoPlaySequenceId": 1,
    "root": node(
        "CCLayer",
        node("CCNode", custom="CCSpriteBatchNode",
             props={"position": prop("Position", {"x": 50, "y": 50}, positionType="Percent"),
                    "contentSize": prop("Size", {"width": 2048, "height": 1536},
                                        sizeType="Absolute")},
             custom_props={"texture": prop("String", "frames"),
                           "isAbsolute": prop("Check", True)}),
        node("CCSprite",
             member={"target": "Owner", "name": "iconPoints"},
             props={
                 "position": prop("Position", {"x": 505.216, "y": -2.3255103},
                                  positionType="RelativeTopRight"),
                 "anchorPoint": prop("Point", {"x": 0.5, "y": 0.4}),
                 "scale": prop("ScaleLock", {"x": -0.5, "y": 0.5}, scaleType="MultiplyResolution"),
                 "rotation": prop("Degrees", 270),
                 "skew": prop("FloatXY", {"x": 10, "y": 0}),
                 "tag": prop("Integer", -7),
                 "visible": prop("Check", False),
                 "displayFrame": prop("SpriteFrame", {"sheet": "", "frame": "icon_citizen.png"}),
                 "opacity": prop("Byte", 128),
                 "color": prop("Color3", [220, 34, 86]),
                 "flip": prop("Flip", {"x": True, "y": False}),
                 "blendFunc": prop("Blendmode", {"src": 770, "dst": 771}),
             },
             animated={
                 "1": {
                     "opacity": {"type": "Byte", "keyframes": [kf(0, 0), kf(0.5, 255)]},
                     "scale": {"type": "ScaleLock", "keyframes": [
                         kf(0, {"x": 0.1, "y": 0.1}, "CubicIn", easingOpt=2),
                         kf(0.25, {"x": 1, "y": 1}, "ElasticOut", easingOpt=0.3)]},
                     "position": {"type": "Position", "keyframes": [
                         kf(0, {"x": 0, "y": 0}, "BackInOut"), kf(1.5, {"x": -40, "y": 12.5})]},
                     "rotation": {"type": "Degrees", "keyframes": [kf(0, 0, "BounceIn")]},
                     "visible": {"type": "Check", "keyframes": [kf(0, False, "Instant"),
                                                                kf(0.1, True, "Instant")]},
                     "color": {"type": "Color3", "keyframes": [kf(0, [255, 255, 255])]},
                     "displayFrame": {"type": "SpriteFrame", "keyframes": [
                         kf(0.2, {"sheet": "", "frame": "clock_city_scene.png"}, "Instant")]},
                     "skew": {"type": "FloatXY", "keyframes": [kf(0, {"x": 0, "y": 5})]},
                 },
                 "0": {"opacity": {"type": "Byte", "keyframes": []}},
             }),
        node("CCMenu",
             node("CCTextButton",
                  member={"target": "Owner", "name": ""},
                  props={
                      "contentSize": prop("Size", {"width": 292, "height": 136},
                                          sizeType="MultiplyResolution"),
                      "block": prop("Block", BLOCK_SOUND),
                      "string": prop("Text", "Прогресс игры будет перезаписан."),
                      "normalFontName": prop("FontTTF", "fonts/Play_button.ttf"),
                      "normalFontSize": prop("FloatScale", 40, scaleType="Absolute"),
                      "selectedFontSize": prop("FloatScale", 20.5,
                                               scaleType="MultiplyResolution"),
                      "normalHorizontalAlignment": prop("IntegerLabeled", 1),
                      "makeCopy": prop("NoValue28", None),
                  }),
             props={"touchEnabled": prop("Check", True, platform="iOS"),
                    "mouseEnabled": prop("Check", True, platform="Mac")}),
        node("CCControlButton",
             props={"ccControl": prop("BlockCCControl", {"selector": "onPress",
                                                         "target": "DocumentRoot",
                                                         "controlEvents": 32}),
                    "title|1": prop("String", "OK"),
                    "preferedSize": prop("Size", {"width": 120, "height": 40},
                                         sizeType="RelativeContainer"),
                    "labelAnchorPoint": prop("PointLock", {"x": 1, "y": -1})}),
        node("CCParticleSystemQuad",
             props={"life": prop("FloatVar", {"base": 3, "variance": 0.25}),
                    "startColor": prop("Color4FVar", {"base": [0.76, 0.25, 0.12, 1],
                                                      "variance": [0, 0, 0, 0]}),
                    "texture": prop("Texture", "ccbResources/ccbParticleFire.png"),
                    "emissionRate": prop("Float", 80.125)}),
        node("CCNode",
             props={"fntFile": prop("FntFile", "fonts/digits.fnt"),
                    "animation": prop("Animation", {"file": "anims.plist", "animation": "run"}),
                    "ccbFile": prop("CCBFile", "popups/other.ccbi")}),
        member={"target": "DocumentRoot", "name": "root"},
        props={"contentSize": prop("Size", {"width": 100, "height": 100}, sizeType="Percent"),
               "ignoreAnchorPointForPosition": prop("Check", True)},
    ),
}


def _body(doc):
    return {k: v for k, v in doc.items() if k != "ccbi"}


def _all_props(doc):
    for n in ccbi.walk(doc["root"]):
        yield from n["properties"].values()
        yield from n["customProperties"].values()


def test_layout_covers_every_type():
    assert {p["type"] for p in _all_props(LAYOUT)} == set(ccbi.PROP_TYPES)
    animated = {t["type"] for n in ccbi.walk(LAYOUT["root"])
                for tracks in n["animatedProperties"].values() for t in tracks.values()}
    assert animated == ccbi.KEYFRAME_TYPES


def test_roundtrip_json_ccbi_json():
    data = ccbi_write.build(LAYOUT)
    doc = ccbi.parse(data)
    assert _body(doc) == LAYOUT                       # float32 505.216 читается как 505.216
    assert doc["ccbi"]["version"] == 5 and doc["ccbi"]["jsControlled"] is False
    assert ccbi_write.build(doc) == data              # с кэшем строк из файла — те же байты


def test_layout_json_rebuilds_same_bytes():
    data = ccbi_write.build(LAYOUT)
    doc = ccbi.layout(data, "1024x768/city/popups/yes_no_popup.ccbi", "obb_patch")
    assert doc["formatVersion"] == 1
    assert doc["source"] == {"layer": "obb_patch", "path": "1024x768/city/popups/yes_no_popup.ccbi"}
    assert doc["resolution"] == {"name": "1024x768", "width": 1024, "height": 768}
    text = ccbi.dumps(doc)
    assert text == ccbi.dumps(ccbi.layout(data, doc["source"]["path"], "obb_patch"))
    assert ccbi_write.build(json.loads(text)) == data
    root = json.loads(text)["root"]
    batch = root["children"][0]
    assert (batch["baseClass"], batch["customClass"]) == ("CCNode", "CCSpriteBatchNode")
    assert (root["baseClass"], root["customClass"]) == ("CCLayer", None)


def test_resolution_metadata():
    assert ccbi.resolution("2048x1536/battle/BattleScene.ccbi") == {
        "name": "2048x1536", "width": 2048, "height": 1536}
    assert ccbi.resolution("fonts/x.ccbi") is None


def test_js_controlled_document():
    doc = {"ccbi": {"version": 5, "jsControlled": True},
           "sequences": [], "autoPlaySequenceId": -1,
           "root": {**node("CCNode", {**node("CCSprite"), "jsController": ""}),
                    "jsController": "MainScene"}}
    parsed = ccbi.parse(ccbi_write.build(doc))
    assert parsed["root"]["jsController"] == "MainScene"
    assert parsed["root"]["children"][0]["jsController"] == ""
    assert parsed["ccbi"]["jsControlled"] is True


def test_canonical_string_cache_when_missing():
    # Как у CocosBuilder: частые строки — в начало кэша, при равенстве — по первому появлению.
    doc = {"sequences": [], "autoPlaySequenceId": -1,
           "root": node("CCNode", props={f"t{i}": prop("Text", "same") for i in (1, 2, 3)})}
    assert ccbi.parse(ccbi_write.build(doc))["ccbi"]["stringCache"] == [
        "same", "CCNode", "t1", "t2", "t3"]


# Файл, собранный вручную по спецификации CCBI v5 + расширения Inferno (docs/formats/ccbi-json.md):
# целые — Elias gamma, биты LSB-first, выравнивание на байт; float — байт вида + значение.
CACHE = ["CCTextButton", "block", "close", "click.wav", "makeCopy", "Default Timeline", "rotation",
         "tag", "CCSprite", "buttonYes", "position", "anchorPoint"]
BLOCK_VALUE = b"\x06\x06" + b"\x04\x01"               # close, Owner + click.wav, true (Inferno)


def _utf(s):
    b = s.encode()
    return len(b).to_bytes(2, "big") + b


def _file(block=BLOCK_VALUE, block_type=b"\xd0\x00", head=b"ibcc\x0c\x00"):
    return b"".join([
        head, b"\x58", *map(_utf, CACHE),              # версия 5, 12 строк
        b"\x02", b"\x04\x50\x01", b"\x0c", b"\x01", b"\x02", b"\x01\x01",  # 1 таймлайн: 10 с, id 0
        b"\x01",                                        # autoPlaySequenceId 0
        b"\x01", b"\x06\x28", b"\x01", b"\x14\x01",     # CCTextButton «buttonYes», 4 свойства
        block_type, b"\x02\x00", block,                 # Block (21)
        b"\x70\x01", b"\x14\x00",                       # тип 28 makeCopy — значения нет
        b"\x0c\x1c\x00", b"\x05", struct.pack("<f", 1.5),  # Degrees rotation 1.5 (float32)
        b"\x1c\x08\x00", b"\x0c",                       # Integer tag −3
        b"\x02",                                        # 1 ребёнок
        b"\x48\x01\x01\x06\x01",                        # CCSprite, 2 свойства
        b"\x01\x68\x00", b"\x02\x03", b"\x14",          # Position (−1, 0.5) Percent
        b"\x06\x18\x00", b"\x00\x01",                   # Point anchorPoint (0, 1)
        b"\x01",                                        # детей нет
    ])


HAND_PARSED = {
    "sequences": [{"sequenceId": 0, "name": "Default Timeline", "duration": 10,
                   "chainedSequenceId": -1, "callbacks": [], "sounds": []}],
    "autoPlaySequenceId": 0,
    "root": node(
        "CCTextButton",
        node("CCSprite",
             props={"position": prop("Position", {"x": -1, "y": 0.5}, positionType="Percent"),
                    "anchorPoint": prop("Point", {"x": 0, "y": 1})}),
        member={"target": "Owner", "name": "buttonYes"},
        props={"block": prop("Block", BLOCK_SOUND),
               "makeCopy": prop("NoValue28", None),
               "rotation": prop("Degrees", 1.5),
               "tag": prop("Integer", -3)}),
    "ccbi": {"version": 5, "jsControlled": False, "stringCache": CACHE},
}


def test_hand_made_inferno_file():
    assert ccbi.parse(_file()) == HAND_PARSED
    assert ccbi_write.build(HAND_PARSED) == _file()


def test_vanilla_block_is_rejected():
    # Стандартный Block без имени звука и флага: поток съезжает, строгий разбор это замечает.
    with pytest.raises(ccbi.CCBIError):
        ccbi.parse(_file(block=b"\x06\x06"))


@pytest.mark.parametrize("data, message", [
    (_file()[:-1], "файл кончился"),
    (_file() + b"\x00", "лишние байты"),
    (_file(head=b"xbcc\x0c\x00"), "это не ccbi"),
    (_file(head=b"ibcc\x14\x00"), "версия формата 4"),
    (_file(block_type=b"\xf0\x00"), "неизвестный тип свойства: 29"),
    (_file(block=b"\x06\x06\x04\x02"), "bool = 2"),
    (_file(block=b"\x06\x04\x04\x01"), "неизвестный target: 3"),
    (_file(block=b"\x46\x06\x04\x01"), "ненулевые биты выравнивания"),
])
def test_strict_errors(data, message):
    with pytest.raises(ccbi.CCBIError, match=message):
        ccbi.parse(data)


@pytest.mark.parametrize("patch, message", [
    ({"properties": {"x": prop("Position", {"x": 0, "y": 0}, positionType="Center")}},
     "positionType"),
    ({"properties": {"x": prop("Vector", 1)}}, "тип свойства"),
    ({"properties": {"x": prop("NoValue28", 1)}}, "NoValue28"),
    ({"memberVarAssignment": {"target": "None", "name": "x"}}, "target None"),
    ({"animatedProperties": {"0": {"x": {"type": "Size", "keyframes": []}}}}, "не анимируется"),
])
def test_writer_rejects_bad_json(patch, message):
    doc = {"sequences": [], "autoPlaySequenceId": -1, "root": {**node("CCNode"), **patch}}
    with pytest.raises(ValueError, match=message):
        ccbi_write.build(doc)


def _variant(text):
    """Макет с одной меткой: так видно, какой слой победил."""
    return ccbi_write.build({"sequences": [], "autoPlaySequenceId": -1,
                             "root": node("CCLabelTTF", props={"string": prop("Text", text)})})


@pytest.fixture
def raw(tmp_path):
    files = {
        "apk/1024x768/splashscreen/splash.ccbi": _variant("apk"),
        "obb_main/1024x768/city/popups/yes_no_popup.ccbi": _variant("main"),
        "obb_main/2048x1536/city/old.ccbi": _variant("hd"),
        "obb_patch/1024x768/city/popups/yes_no_popup.ccbi": _variant("patch"),
    }
    for rel, data in files.items():
        layer, path = rel.split("/", 1)
        dst = tmp_path / "raw" / layer / "assets" / "interface" / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
    (tmp_path / "raw/obb_main/assets/interface/interface.xml").write_text("<interfaces/>")
    return tmp_path / "raw"


def test_convert_with_layer_override(raw, tmp_path):
    out = tmp_path / "ui"
    docs = ccbi.convert(raw, out)
    assert sorted(docs) == ["1024x768/city/popups/yes_no_popup.ccbi",
                            "1024x768/splashscreen/splash.ccbi", "2048x1536/city/old.ccbi"]
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert files == ["1024x768/city/popups/yes_no_popup.json", "1024x768/splashscreen/splash.json",
                     "2048x1536/city/old.json"]
    popup = json.loads((out / "1024x768/city/popups/yes_no_popup.json").read_text())
    assert popup["source"] == {"layer": "obb_patch",
                               "path": "1024x768/city/popups/yes_no_popup.ccbi"}
    assert popup["root"]["properties"]["string"]["value"] == "patch"
    old = json.loads((out / "2048x1536/city/old.json").read_text())
    assert old["resolution"] == {"name": "2048x1536", "width": 2048, "height": 1536}


def test_cli_convert(raw, tmp_path, capsys):
    assert ccbi.main(["--raw", str(raw), "--out", str(tmp_path / "ui")]) == 0
    out = capsys.readouterr().out
    assert "макетов: 3 (1024x768 2, 2048x1536 1)" in out
    assert "1024x768: узлов 2; CCLabelTTF 2" in out


def test_cli_without_raw(tmp_path):
    with pytest.raises(SystemExit, match="extract_xapk"):
        ccbi.main(["--raw", str(tmp_path / "raw"), "--out", str(tmp_path / "ui")])
    assert not (tmp_path / "ui").exists()


def test_check(raw, capsys, monkeypatch):
    monkeypatch.setitem(ccbi.EXPECTED, "files", {"apk": 1, "obb_main": 2, "obb_patch": 1})
    monkeypatch.setitem(ccbi.EXPECTED, "effective", {"1024x768": 2, "2048x1536": 1})
    monkeypatch.setitem(ccbi.EXPECTED, "blocks", 0)
    monkeypatch.setitem(ccbi.EXPECTED, "blocks_with_sound", 0)
    monkeypatch.setitem(ccbi.EXPECTED, "novalue28", 0)
    monkeypatch.setitem(ccbi.EXPECTED, "novalue28_paths", 0)
    monkeypatch.setitem(ccbi.EXPECTED, "classes_all", {"CCLabelTTF": 4})
    monkeypatch.setitem(ccbi.EXPECTED, "classes_1024x768", {"CCLabelTTF": 2})
    assert ccbi.check(raw) == []
    out = capsys.readouterr().out
    assert "файлов: 4" in out and "байт в байт: 4" in out and "совпало с отчётом" in out

    (raw / "apk/assets/interface/1024x768/splashscreen/splash.ccbi").write_bytes(b"ibcc")
    assert ccbi.main(["--check", "--raw", str(raw)]) == 1
    out = capsys.readouterr().out
    assert "[!] не разобран" in out and "НЕ совпало с отчётом" in out


def test_write_cli(tmp_path, capsys):
    src, dst = tmp_path / "layout.json", tmp_path / "layout.ccbi"
    src.write_text(ccbi.dumps(ccbi.layout(ccbi_write.build(LAYOUT), "1024x768/a.ccbi")))
    ccbi_write.main([str(src), str(dst)])
    assert dst.read_bytes() == ccbi_write.build(LAYOUT)
    assert "байт" in capsys.readouterr().out
