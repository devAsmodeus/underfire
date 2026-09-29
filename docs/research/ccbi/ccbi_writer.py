#!/usr/bin/env python3
"""
JSON (из ccbi_parser) -> .ccbi. Нужен для двух вещей:

1. Проверка парсера: parse -> write с тем же кэшем строк -> байт-в-байт с оригиналом.
2. Конвертация диалекта Inferno в стандартный CCBI v5 ("vanilla"), который читают
   штатные ридеры (cocos2d-html5 CCBReader.js, cocos2d-x): у Block отбрасываются
   soundFile/soundEnabled, свойства типа 28 (makeCopy) выкидываются.

    python3 ccbi_writer.py --roundtrip               # проверить все 306 файлов
    python3 ccbi_writer.py --to-vanilla in.ccbi out.ccbi
"""
from __future__ import annotations

import glob
import struct
import sys
from typing import Any

import ccbi_parser as P

RAW = "raw"


def _idx(table, v):
    return table.index(v) if isinstance(v, str) else int(v)


GL_BLEND_REV = {v: k for k, v in P.GL_BLEND.items()}


class Writer:
    def __init__(self, strings: list[str], dialect: str = "inferno"):
        self.out = bytearray()
        self.strings = strings
        self.lookup = {s: i for i, s in enumerate(strings)}
        self.dialect = dialect

    # ---- базовые типы
    def byte(self, b: int):
        self.out.append(b & 0xFF)

    def bool(self, b: bool):
        self.byte(1 if b else 0)

    def uint(self, n: int, signed: bool = False):
        if signed:
            num = (-n) * 2 if n < 0 else n * 2 + 1
        else:
            num = n + 1
        assert num > 0
        nbits = num.bit_length() - 1
        bits = [0] * nbits + [1] + [(num >> a) & 1 for a in range(nbits - 1, -1, -1)]
        nbytes = (len(bits) + 7) // 8
        buf = bytearray(nbytes)
        for i, bit in enumerate(bits):
            if bit:
                buf[i // 8] |= 1 << (i % 8)
        self.out += buf

    def sint(self, n: int):
        self.uint(n, True)

    def float(self, f: float):
        if f == 0:
            self.byte(0)
        elif f == 1:
            self.byte(1)
        elif f == -1:
            self.byte(2)
        elif f == 0.5:
            self.byte(3)
        elif int(f) == f:
            self.byte(4)
            self.sint(int(f))
        else:
            self.byte(5)
            self.out += struct.pack("<f", f)

    def utf8(self, s: str):
        b = s.encode("utf-8")
        self.out += bytes([(len(b) >> 8) & 0xFF, len(b) & 0xFF]) + b

    def cstr(self, s: str):
        if s not in self.lookup:
            self.lookup[s] = len(self.strings)
            self.strings.append(s)
        self.uint(self.lookup[s])

    # ---- значения
    def value(self, ptype: str, v: Any):
        if ptype == "Position":
            self.float(v["x"]); self.float(v["y"]); self.uint(_idx(P.POSITION_TYPES, v["type"]))
        elif ptype == "Size":
            self.float(v["w"]); self.float(v["h"]); self.uint(_idx(P.SIZE_TYPES, v["type"]))
        elif ptype in ("Point", "PointLock", "FloatXY"):
            self.float(v[0]); self.float(v[1])
        elif ptype == "FloatVar":
            self.float(v["value"]); self.float(v["var"])
        elif ptype == "ScaleLock":
            self.float(v["x"]); self.float(v["y"]); self.uint(_idx(P.SCALE_TYPES, v["type"]))
        elif ptype in ("Degrees", "Float"):
            self.float(v)
        elif ptype == "FloatScale":
            self.float(v["value"]); self.uint(_idx(P.SCALE_TYPES, v["type"]))
        elif ptype in ("Integer", "IntegerLabeled"):
            self.sint(v)
        elif ptype == "Check":
            self.bool(v)
        elif ptype == "Byte":
            self.byte(v)
        elif ptype == "SpriteFrame":
            self.cstr(v["sheet"]); self.cstr(v["frame"])
        elif ptype == "Animation":
            self.cstr(v["file"]); self.cstr(v["animation"])
        elif ptype in ("Texture", "FntFile", "CCBFile", "Text", "String", "FontTTF"):
            self.cstr(v)
        elif ptype == "Color3":
            for c in v:
                self.byte(c)
        elif ptype == "Color4FVar":
            for c in v["color"] + v["var"]:
                self.float(c)
        elif ptype == "Flip":
            self.bool(v[0]); self.bool(v[1])
        elif ptype == "Blendmode":
            self.uint(GL_BLEND_REV.get(v["src"], v["src"])); self.uint(GL_BLEND_REV.get(v["dst"], v["dst"]))
        elif ptype == "Block":
            self.cstr(v["selector"]); self.uint(_idx(P.TARGET_TYPES, v["target"]))
            if self.dialect == "inferno":
                self.cstr(v.get("soundFile", "")); self.bool(v.get("soundEnabled", False))
        elif ptype == "BlockCCControl":
            self.cstr(v["selector"]); self.uint(_idx(P.TARGET_TYPES, v["target"])); self.uint(v["eventMask"])
        elif ptype == "NoValue28":
            pass
        else:
            raise ValueError(ptype)

    def kf_value(self, ptype: str, v: Any):
        if ptype == "Check":
            self.bool(v)
        elif ptype == "Byte":
            self.byte(v)
        elif ptype == "Color3":
            for c in v:
                self.byte(c)
        elif ptype == "Degrees":
            self.float(v)
        elif ptype in ("ScaleLock", "Position", "FloatXY"):
            self.float(v[0]); self.float(v[1])
        elif ptype == "SpriteFrame":
            self.cstr(v["sheet"]); self.cstr(v["frame"])
        else:
            raise ValueError(ptype)

    def node(self, n: dict, js: bool):
        self.cstr(n["class"])
        if js:
            self.cstr(n.get("jsController", ""))
        mv = n.get("memberVar")
        if mv:
            self.uint(_idx(P.TARGET_TYPES, mv["target"])); self.cstr(mv["name"])
        else:
            self.uint(0)
        anim = n.get("animated", {})
        self.uint(len(anim))
        for sid, props in anim.items():
            self.uint(int(sid))
            self.uint(len(props))
            for pname, pv in props.items():
                self.cstr(pname)
                ptype = pv["type"]
                self.uint(P.PROP_TYPES.index(ptype))
                self.uint(len(pv["keyframes"]))
                for kf in pv["keyframes"]:
                    self.float(kf["time"])
                    e = _idx(P.EASING, kf["easing"])
                    self.uint(e)
                    if e in P.EASING_WITH_OPT:
                        self.float(kf.get("easingOpt", 0))
                    self.kf_value(ptype, kf["value"])
        props = n["props"]
        if self.dialect == "vanilla":
            props = [p for p in props if p["type"] != "NoValue28"]
        reg = [p for p in props if not p.get("custom")]
        ext = [p for p in props if p.get("custom")]
        self.uint(len(reg)); self.uint(len(ext))
        for p in reg + ext:
            self.uint(P.PROP_TYPES.index(p["type"]))
            self.cstr(p["name"])
            self.byte(P.PLATFORMS.index(p.get("platform", "All")))
            self.value(p["type"], p["value"])
        ch = n.get("children", [])
        self.uint(len(ch))
        for c in ch:
            self.node(c, js)

    def document(self, doc: dict) -> bytes:
        # тело пишем отдельно, чтобы кэш строк (возможно дополненный) оказался в начале
        b = Writer(self.strings, self.dialect)
        b.uint(len(doc["sequences"]))
        for s in doc["sequences"]:
            b.float(s["duration"]); b.cstr(s["name"]); b.uint(s["sequenceId"]); b.sint(s["chainedSequenceId"])
            cbs = s.get("callbacks", [])
            b.uint(len(cbs))
            for c in cbs:
                b.float(c["time"]); b.cstr(c["selector"]); b.uint(_idx(P.TARGET_TYPES, c["target"]))
            snd = s.get("sounds", [])
            b.uint(len(snd))
            for c in snd:
                b.float(c["time"]); b.cstr(c["sound"]); b.float(c["pitch"]); b.float(c["pan"]); b.float(c["gain"])
        b.sint(doc["autoPlaySequenceId"])
        b.node(doc["root"], doc["jsControlled"])
        head = Writer(self.strings, self.dialect)
        head.out += P.MAGIC
        head.uint(doc["version"])
        head.bool(doc["jsControlled"])
        head.uint(len(self.strings))
        for s in self.strings:
            head.utf8(s)
        return bytes(head.out + b.out)


def parse_with_strings(path: str):
    data = open(path, "rb").read()
    r = P.CCBIReader(data, path)
    doc = r.read_document()
    return data, doc, list(r.strings)


def roundtrip_all() -> int:
    files = sorted(glob.glob(f"{RAW}/*/assets/interface/**/*.ccbi", recursive=True))
    bad = 0
    for f in files:
        data, doc, strings = parse_with_strings(f)
        out = Writer(strings).document(doc)
        if out != data:
            bad += 1
            print("MISMATCH", f)
    print(f"round-trip: {len(files) - bad}/{len(files)} байт-в-байт")
    # примеры CocosBuilder (vanilla)
    ex = sorted(glob.glob("refs/CocosBuilder/Examples/CocosBuilderExample/Resources/**/*.ccbi", recursive=True))
    ok = 0
    for f in ex:
        data = open(f, "rb").read()
        r = P.CCBIReader(data, f, "vanilla")
        doc = r.read_document()
        ok += Writer(list(r.strings), "vanilla").document(doc) == data
    if ex:
        print(f"round-trip CocosBuilder examples (vanilla): {ok}/{len(ex)}")
    # конвертация inferno -> vanilla должна читаться строгим vanilla-ридером
    conv_ok = 0
    for f in files:
        data, doc, strings = parse_with_strings(f)
        v = Writer(strings, "vanilla").document(doc)
        try:
            P.parse_bytes(v, f, "vanilla")
            conv_ok += 1
        except Exception as e:  # noqa: BLE001
            print("VANILLA FAIL", f, e)
    print(f"inferno -> vanilla: {conv_ok}/{len(files)} читаются стандартным ридером")
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--roundtrip"]:
        sys.exit(roundtrip_all())
    if sys.argv[1:2] == ["--to-vanilla"] and len(sys.argv) == 4:
        data, doc, strings = parse_with_strings(sys.argv[2])
        open(sys.argv[3], "wb").write(Writer(strings, "vanilla").document(doc))
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
