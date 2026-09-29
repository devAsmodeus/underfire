#!/usr/bin/env python3
"""
CocosBuilder .ccbi (binary, format version 5) -> JSON.

Порт эталонного ридера cocos2d-x v2 (extensions/CCBReader/CCBReader.cpp,
CCNodeLoader.cpp) и писателя CocosBuilder 3.x
(CocosBuilder/Cocos2D iPhone/CCBXCocos2diPhoneWriter.m, kCCBXVersion 5).

Диалект "inferno" (по умолчанию) — расширения RJ Games / движка Inferno,
проверены дизассемблированием libinferno.so (CCNodeLoader::parsePropTypeBlock,
CCNodeLoader::parseProperties):
  * Block (тип 21): после selector + target ещё soundFile (CSTRING) и
    soundEnabled (BOOL) -> CCMenuItem::setSoundFile / setSoundEnabled;
  * тип 28: свойство без значения (в switch движка — пустой case; в наших
    файлах это только "makeCopy" у CCTextButton, т. е. кнопка редактора).
Диалект "vanilla" — стандартный CocosBuilder 3.x (для проверки на примерах).

Парсер строгий: неизвестный тип свойства / тип float / выход за конец файла /
лишние байты в конце — это ошибка (так проверяется, что формат понят верно).

Использование:
    python3 ccbi_parser.py file.ccbi            # JSON в stdout
    python3 ccbi_parser.py file.ccbi -o out.json
    python3 ccbi_parser.py --vanilla file.ccbi  # стандартный CocosBuilder
"""
from __future__ import annotations

import json
import struct
import sys
from typing import Any

MAGIC = b"ibcc"  # int 'ccbi', записанный little-endian
SUPPORTED_VERSION = 5

# Порядок = id типа свойства (CCBReader.h: kCCBPropType*, writer: setupPropTypes)
PROP_TYPES = [
    "Position", "Size", "Point", "PointLock", "ScaleLock", "Degrees", "Integer",
    "Float", "FloatVar", "Check", "SpriteFrame", "Texture", "Byte", "Color3",
    "Color4FVar", "Flip", "Blendmode", "FntFile", "Text", "FontTTF",
    "IntegerLabeled", "Block", "Animation", "CCBFile", "String",
    "BlockCCControl", "FloatScale", "FloatXY",
    "NoValue28",  # расширение Inferno: без полезной нагрузки
]
PT = {name: i for i, name in enumerate(PROP_TYPES)}

POSITION_TYPES = ["RelativeBottomLeft", "RelativeTopLeft", "RelativeTopRight",
                  "RelativeBottomRight", "Percent", "MultiplyResolution"]
SIZE_TYPES = ["Absolute", "Percent", "RelativeContainer", "HorizontalPercent",
              "VerticalPercent", "MultiplyResolution"]
SCALE_TYPES = ["Absolute", "MultiplyResolution"]
PLATFORMS = ["All", "iOS", "Mac"]
TARGET_TYPES = ["None", "DocumentRoot", "Owner"]
EASING = ["Instant", "Linear", "CubicIn", "CubicOut", "CubicInOut",
          "ElasticIn", "ElasticOut", "ElasticInOut", "BounceIn", "BounceOut",
          "BounceInOut", "BackIn", "BackOut", "BackInOut"]
EASING_WITH_OPT = {2, 3, 4, 5, 6, 7}

# CCControl events (CCControl.h): битовая маска
CONTROL_EVENTS = ["TouchDown", "TouchDragInside", "TouchDragOutside",
                  "TouchDragEnter", "TouchDragExit", "TouchUpInside",
                  "TouchUpOutside", "TouchCancel", "ValueChanged"]

# GL blend factors -> имена (для читаемости)
GL_BLEND = {0: "GL_ZERO", 1: "GL_ONE", 0x300: "GL_SRC_COLOR",
            0x301: "GL_ONE_MINUS_SRC_COLOR", 0x302: "GL_SRC_ALPHA",
            0x303: "GL_ONE_MINUS_SRC_ALPHA", 0x304: "GL_DST_ALPHA",
            0x305: "GL_ONE_MINUS_DST_ALPHA", 0x306: "GL_DST_COLOR",
            0x307: "GL_ONE_MINUS_DST_COLOR"}


class CCBIError(Exception):
    pass


def _short_f32(f: float, raw: bytes) -> float:
    """Кратчайшая десятичная запись, которая обратно даёт тот же float32 (без потерь)."""
    for prec in range(6, 10):
        cand = float(f"{f:.{prec}g}")
        if struct.pack("<f", cand) == raw:
            return cand
    return f


def _name(table: list[str], idx: int) -> Any:
    return table[idx] if 0 <= idx < len(table) else idx


def _events(mask: int) -> list[str]:
    return [n for i, n in enumerate(CONTROL_EVENTS) if mask & (1 << i)]


class CCBIReader:
    def __init__(self, data: bytes, name: str = "?", dialect: str = "inferno"):
        if dialect not in ("inferno", "vanilla"):
            raise ValueError(dialect)
        self.dialect = dialect
        self.data = data
        self.name = name
        self.pos = 0
        self.bit = 0
        self.strings: list[str] = []
        self.js_controlled = False
        self.version = None

    # ---------------- базовые типы ----------------
    def _need(self, n: int):
        if self.pos + n > len(self.data):
            raise CCBIError(f"{self.name}: unexpected EOF at {self.pos} (need {n})")

    def read_byte(self) -> int:
        self._need(1)
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_bool(self) -> bool:
        return self.read_byte() != 0

    def _get_bit(self) -> bool:
        self._need(1)
        v = bool(self.data[self.pos] & (1 << self.bit))
        self.bit += 1
        if self.bit >= 8:
            self.bit = 0
            self.pos += 1
        return v

    def _align(self):
        if self.bit:
            self.bit = 0
            self.pos += 1

    def read_int(self, signed: bool) -> int:
        """Elias gamma, биты LSB-first, выравнивание на байт после числа."""
        num_bits = 0
        while not self._get_bit():
            num_bits += 1
            if num_bits > 40:
                raise CCBIError(f"{self.name}: bad varint at {self.pos}")
        current = 0
        for a in range(num_bits - 1, -1, -1):
            if self._get_bit():
                current |= 1 << a
        current |= 1 << num_bits
        self._align()
        if signed:
            return current // 2 if current % 2 else -(current // 2)
        return current - 1

    def read_float(self) -> float:
        t = self.read_byte()
        if t == 0:
            return 0.0
        if t == 1:
            return 1.0
        if t == 2:
            return -1.0
        if t == 3:
            return 0.5
        if t == 4:
            return float(self.read_int(True))
        if t == 5:
            self._need(4)
            raw = self.data[self.pos:self.pos + 4]
            (f,) = struct.unpack("<f", raw)
            self.pos += 4
            return _short_f32(f, raw)
        raise CCBIError(f"{self.name}: bad float type {t} at {self.pos - 1}")

    def read_utf8(self) -> str:
        b0, b1 = self.read_byte(), self.read_byte()
        n = (b0 << 8) | b1
        self._need(n)
        s = self.data[self.pos:self.pos + n].decode("utf-8")
        self.pos += n
        return s

    def read_cstr(self) -> str:
        i = self.read_int(False)
        if i >= len(self.strings):
            raise CCBIError(f"{self.name}: string index {i} out of range at {self.pos}")
        return self.strings[i]

    # ---------------- структура ----------------
    def read_header(self) -> dict:
        self._need(4)
        if self.data[:4] != MAGIC:
            raise CCBIError(f"{self.name}: bad magic {self.data[:4]!r}")
        self.pos = 4
        self.version = self.read_int(False)
        if self.version != SUPPORTED_VERSION:
            raise CCBIError(f"{self.name}: unsupported version {self.version}")
        self.js_controlled = self.read_bool()
        return {"version": self.version, "jsControlled": self.js_controlled}

    def read_string_cache(self):
        n = self.read_int(False)
        self.strings = [self.read_utf8() for _ in range(n)]

    def read_sequences(self) -> dict:
        seqs = []
        for _ in range(self.read_int(False)):
            seq = {
                "duration": self.read_float(),
                "name": self.read_cstr(),
                "sequenceId": self.read_int(False),
                "chainedSequenceId": self.read_int(True),
            }
            cbs = []
            for _ in range(self.read_int(False)):
                t = self.read_float()
                name = self.read_cstr()
                target = self.read_int(False)
                cbs.append({"time": t, "selector": name,
                            "target": _name(TARGET_TYPES, target)})
            snds = []
            for _ in range(self.read_int(False)):
                snds.append({"time": self.read_float(), "sound": self.read_cstr(),
                             "pitch": self.read_float(), "pan": self.read_float(),
                             "gain": self.read_float()})
            if cbs:
                seq["callbacks"] = cbs
            if snds:
                seq["sounds"] = snds
            seqs.append(seq)
        autoplay = self.read_int(True)
        return {"sequences": seqs, "autoPlaySequenceId": autoplay}

    def read_keyframe_value(self, ptype: int) -> Any:
        if ptype == PT["Check"]:
            return self.read_bool()
        if ptype == PT["Byte"]:
            return self.read_byte()
        if ptype == PT["Color3"]:
            return [self.read_byte(), self.read_byte(), self.read_byte()]
        if ptype == PT["Degrees"]:
            return self.read_float()
        if ptype in (PT["ScaleLock"], PT["Position"], PT["FloatXY"]):
            return [self.read_float(), self.read_float()]
        if ptype == PT["SpriteFrame"]:
            return {"sheet": self.read_cstr(), "frame": self.read_cstr()}
        raise CCBIError(f"{self.name}: unsupported animated prop type {ptype} at {self.pos}")

    def read_keyframe(self, ptype: int) -> dict:
        kf = {"time": self.read_float()}
        easing = self.read_int(False)
        kf["easing"] = _name(EASING, easing)
        if easing in EASING_WITH_OPT:
            kf["easingOpt"] = self.read_float()
        kf["value"] = self.read_keyframe_value(ptype)
        return kf

    def read_property_value(self, ptype: int) -> Any:
        r = self
        if ptype == PT["Position"]:
            x, y = r.read_float(), r.read_float()
            return {"x": x, "y": y, "type": _name(POSITION_TYPES, r.read_int(False))}
        if ptype == PT["Size"]:
            w, h = r.read_float(), r.read_float()
            return {"w": w, "h": h, "type": _name(SIZE_TYPES, r.read_int(False))}
        if ptype in (PT["Point"], PT["PointLock"], PT["FloatXY"]):
            return [r.read_float(), r.read_float()]
        if ptype == PT["FloatVar"]:
            return {"value": r.read_float(), "var": r.read_float()}
        if ptype == PT["ScaleLock"]:
            x, y = r.read_float(), r.read_float()
            return {"x": x, "y": y, "type": _name(SCALE_TYPES, r.read_int(False))}
        if ptype in (PT["Degrees"], PT["Float"]):
            return r.read_float()
        if ptype == PT["FloatScale"]:
            f = r.read_float()
            return {"value": f, "type": _name(SCALE_TYPES, r.read_int(False))}
        if ptype in (PT["Integer"], PT["IntegerLabeled"]):
            return r.read_int(True)
        if ptype == PT["Check"]:
            return r.read_bool()
        if ptype == PT["Byte"]:
            return r.read_byte()
        if ptype == PT["SpriteFrame"]:
            return {"sheet": r.read_cstr(), "frame": r.read_cstr()}
        if ptype == PT["Animation"]:
            return {"file": r.read_cstr(), "animation": r.read_cstr()}
        if ptype in (PT["Texture"], PT["FntFile"], PT["CCBFile"],
                     PT["Text"], PT["String"], PT["FontTTF"]):
            return r.read_cstr()
        if ptype == PT["Color3"]:
            return [r.read_byte(), r.read_byte(), r.read_byte()]
        if ptype == PT["Color4FVar"]:
            vals = [r.read_float() for _ in range(8)]
            return {"color": vals[:4], "var": vals[4:]}
        if ptype == PT["Flip"]:
            return [r.read_bool(), r.read_bool()]
        if ptype == PT["Blendmode"]:
            s, d = r.read_int(False), r.read_int(False)
            return {"src": GL_BLEND.get(s, s), "dst": GL_BLEND.get(d, d)}
        if ptype == PT["Block"]:
            sel = r.read_cstr()
            v = {"selector": sel, "target": _name(TARGET_TYPES, r.read_int(False))}
            if self.dialect == "inferno":
                v["soundFile"] = r.read_cstr()
                v["soundEnabled"] = r.read_bool()
            return v
        if ptype == PT["NoValue28"]:
            if self.dialect != "inferno":
                raise CCBIError(f"{self.name}: property type 28 in vanilla dialect")
            return None
        if ptype == PT["BlockCCControl"]:
            sel = r.read_cstr()
            tgt = r.read_int(False)
            ev = r.read_int(False)
            return {"selector": sel, "target": _name(TARGET_TYPES, tgt),
                    "events": _events(ev), "eventMask": ev}
        raise CCBIError(f"{self.name}: unknown property type {ptype} at {self.pos}")

    def read_node(self, depth: int = 0) -> dict:
        if depth > 64:
            raise CCBIError(f"{self.name}: node graph too deep")
        node: dict[str, Any] = {"class": self.read_cstr()}
        if self.js_controlled:
            node["jsController"] = self.read_cstr()
        mtype = self.read_int(False)
        if mtype != 0:
            node["memberVar"] = {"target": _name(TARGET_TYPES, mtype),
                                 "name": self.read_cstr()}
        # анимированные свойства: seqId -> {prop -> {type, keyframes}}
        n_seq = self.read_int(False)
        if n_seq:
            anim = {}
            for _ in range(n_seq):
                seq_id = self.read_int(False)
                props = {}
                for _ in range(self.read_int(False)):
                    pname = self.read_cstr()
                    ptype = self.read_int(False)
                    kfs = [self.read_keyframe(ptype) for _ in range(self.read_int(False))]
                    props[pname] = {"type": _name(PROP_TYPES, ptype), "keyframes": kfs}
                anim[str(seq_id)] = props
            node["animated"] = anim
        n_reg = self.read_int(False)
        n_extra = self.read_int(False)
        props = []
        for i in range(n_reg + n_extra):
            ptype = self.read_int(False)
            pname = self.read_cstr()
            platform = self.read_byte()
            if ptype >= len(PROP_TYPES):
                raise CCBIError(f"{self.name}: unknown property type id {ptype} "
                                f"({pname!r}) at {self.pos}")
            if platform > 2:
                raise CCBIError(f"{self.name}: bad platform {platform} at {self.pos}")
            value = self.read_property_value(ptype)
            p = {"name": pname, "type": PROP_TYPES[ptype], "value": value}
            if platform:
                p["platform"] = PLATFORMS[platform]
            if i >= n_reg:
                p["custom"] = True
            props.append(p)
        node["props"] = props
        n_children = self.read_int(False)
        if n_children:
            node["children"] = [self.read_node(depth + 1) for _ in range(n_children)]
        return node

    def read_document(self) -> dict:
        header = self.read_header()
        self.read_string_cache()
        seqs = self.read_sequences()
        root = self.read_node()
        if self.bit != 0 or self.pos != len(self.data):
            raise CCBIError(f"{self.name}: trailing data: pos={self.pos} bit={self.bit} "
                            f"size={len(self.data)}")
        return {**header, "stringCacheSize": len(self.strings), **seqs, "root": root}


def parse_bytes(data: bytes, name: str = "?", dialect: str = "inferno") -> dict:
    return CCBIReader(data, name, dialect).read_document()


def parse_file(path: str, dialect: str = "inferno") -> dict:
    with open(path, "rb") as fh:
        return parse_bytes(fh.read(), path, dialect)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    out = None
    dialect = "inferno"
    if "--vanilla" in argv:
        argv = [a for a in argv if a != "--vanilla"]
        dialect = "vanilla"
    if "-o" in argv:
        i = argv.index("-o")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    doc = parse_file(argv[0], dialect)
    text = json.dumps(doc, ensure_ascii=False, indent=1)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
