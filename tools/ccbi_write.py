#!/usr/bin/env python3
"""Обратная запись: JSON макета (формат tools/ccbi_to_json.py) → .ccbi (CCBI v5, вариант Inferno).

Нужна, чтобы доказать, что разбор без потерь: `ccbi_to_json.py --check` собирает каждый из 306
файлов игры обратно и сравнивает байты, а тесты гоняют синтетические макеты JSON → .ccbi → JSON.
Кодирование — как у писателя CocosBuilder (CCBXCocos2diPhoneWriter.m): целые — Elias gamma,
float — самым коротким из шести видов. Кэш строк берётся из ccbi.stringCache: там порядок
оригинала и строки, на которые файл не ссылается. Если кэша нет (синтетический макет), он
строится как у CocosBuilder: по убыванию числа ссылок, при равенстве — по первому появлению.

    python3 tools/ccbi_write.py assets/ui/1024x768/city/popups/yes_no_popup.json out.ccbi
Вход  : JSON макета (обязательны sequences, autoPlaySequenceId, root; ccbi — по желанию)
Выход : .ccbi
"""
from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

from ccbi_to_json import (
    CCBI_VERSION,
    EASINGS,
    EASINGS_WITH_OPT,
    KEYFRAME_TYPES,
    MAGIC,
    PLATFORMS,
    POSITION_TYPES,
    PROP_TYPES,
    SCALE_TYPES,
    SIZE_TYPES,
    STRING_TYPES,
    TARGETS,
)


def _index(table: tuple[str, ...], value: str, what: str) -> int:
    try:
        return table.index(value)
    except ValueError:
        raise ValueError(f"неизвестный {what}: {value!r}") from None


class _Writer:
    """Поток CCBI. Без index — первый проход: только считает ссылки на строки."""

    def __init__(self, index: dict[str, int] | None = None, js_controlled: bool = False):
        self.out = bytearray()
        self.index = index
        self.used: Counter[str] = Counter()
        self.js_controlled = js_controlled

    # ---- базовые типы
    def byte(self, b: int) -> None:
        if not 0 <= b <= 255:
            raise ValueError(f"байт вне 0…255: {b}")
        self.out.append(b)

    def bool(self, b: bool) -> None:
        if not isinstance(b, bool):
            raise ValueError(f"ожидался bool: {b!r}")
        self.out.append(int(b))

    def _gamma(self, num: int) -> None:
        """Elias gamma: (n−1) нулей, затем n бит числа старшими вперёд; биты LSB-first."""
        bits = "0" * (num.bit_length() - 1) + format(num, "b")
        for i in range(0, len(bits), 8):
            self.out.append(sum(1 << j for j, c in enumerate(bits[i:i + 8]) if c == "1"))

    def uint(self, n: int) -> None:
        if n < 0:
            raise ValueError(f"отрицательное беззнаковое: {n}")
        self._gamma(n + 1)

    def sint(self, n: int) -> None:
        self._gamma(n * 2 + 1 if n >= 0 else -n * 2)

    def float(self, f: float) -> None:
        f = float(f)
        if f in (0, 1, -1, 0.5):                      # −0.0 == 0, как у CocosBuilder
            self.byte((0, 1, -1, 0.5).index(f))
        elif f.is_integer() and -2 ** 31 <= f < 2 ** 31:   # ((int)f) == f в Objective-C
            self.byte(4)
            self.sint(int(f))
        else:
            self.byte(5)
            self.out += struct.pack("<f", f)

    def utf8(self, s: str) -> None:
        b = s.encode("utf-8")
        if len(b) > 0xFFFF:
            raise ValueError(f"строка длиннее 65535 байт: {s[:40]!r}…")
        self.out += len(b).to_bytes(2, "big") + b

    def cstr(self, s: str) -> None:
        if not isinstance(s, str):
            raise ValueError(f"ожидалась строка: {s!r}")
        if self.index is None:
            self.used[s] += 1
            self.uint(0)
        else:
            self.uint(self.index[s])

    # ---- структура
    def sequences(self, doc: dict) -> None:
        self.uint(len(doc["sequences"]))
        for seq in doc["sequences"]:
            self.float(seq["duration"])
            self.cstr(seq["name"])
            self.uint(seq["sequenceId"])
            self.sint(seq["chainedSequenceId"])
            self.uint(len(seq["callbacks"]))
            for cb in seq["callbacks"]:
                self.float(cb["time"])
                self.cstr(cb["selector"])
                self.uint(_index(TARGETS, cb["target"], "target"))
            self.uint(len(seq["sounds"]))
            for snd in seq["sounds"]:
                self.float(snd["time"])
                self.cstr(snd["file"])
                self.float(snd["pitch"])
                self.float(snd["pan"])
                self.float(snd["gain"])
        self.sint(doc["autoPlaySequenceId"])

    def node(self, node: dict) -> None:
        self.cstr(node.get("customClass") or node["baseClass"])
        if self.js_controlled:
            self.cstr(node.get("jsController", ""))
        member = node.get("memberVarAssignment")
        if member is None:
            self.uint(0)
        else:
            target = _index(TARGETS, member["target"], "target")
            if target == 0:
                raise ValueError("memberVarAssignment с target None: имя в файл не попадёт")
            self.uint(target)
            self.cstr(member["name"])
        animated = node.get("animatedProperties", {})
        self.uint(len(animated))
        for seq_id, tracks in animated.items():
            self.uint(int(seq_id))
            self.uint(len(tracks))
            for name, track in tracks.items():
                ptype = track["type"]
                if ptype not in KEYFRAME_TYPES:
                    raise ValueError(f"тип {ptype} не анимируется ({name})")
                self.cstr(name)
                self.uint(PROP_TYPES.index(ptype))
                self.uint(len(track["keyframes"]))
                for kf in track["keyframes"]:
                    self.keyframe(ptype, kf)
        regular = node.get("properties", {})
        custom = node.get("customProperties", {})
        self.uint(len(regular))
        self.uint(len(custom))
        for name, prop in [*regular.items(), *custom.items()]:
            self.uint(_index(PROP_TYPES, prop["type"], "тип свойства"))
            self.cstr(name)
            self.byte(_index(PLATFORMS, prop.get("platform", "All"), "platform"))
            self.prop(prop)
        children = node.get("children", [])
        self.uint(len(children))
        for child in children:
            self.node(child)

    def keyframe(self, ptype: str, kf: dict) -> None:
        self.float(kf["time"])
        easing = _index(EASINGS, kf["easing"], "easing")
        self.uint(easing)
        if EASINGS[easing] in EASINGS_WITH_OPT:
            self.float(kf["easingOpt"])
        v = kf["value"]
        if ptype == "Check":
            self.bool(v)
        elif ptype == "Byte":
            self.byte(v)
        elif ptype == "Color3":
            for c in v:
                self.byte(c)
        elif ptype == "Degrees":
            self.float(v)
        elif ptype == "SpriteFrame":
            self.cstr(v["sheet"])
            self.cstr(v["frame"])
        else:                                         # ScaleLock, Position, FloatXY
            self.float(v["x"])
            self.float(v["y"])

    def prop(self, p: dict) -> None:
        ptype, v = p["type"], p["value"]
        if ptype == "Position":
            self.float(v["x"])
            self.float(v["y"])
            self.uint(_index(POSITION_TYPES, p["positionType"], "positionType"))
        elif ptype == "Size":
            self.float(v["width"])
            self.float(v["height"])
            self.uint(_index(SIZE_TYPES, p["sizeType"], "sizeType"))
        elif ptype == "ScaleLock":
            self.float(v["x"])
            self.float(v["y"])
            self.uint(_index(SCALE_TYPES, p["scaleType"], "scaleType"))
        elif ptype == "FloatScale":
            self.float(v)
            self.uint(_index(SCALE_TYPES, p["scaleType"], "scaleType"))
        elif ptype in ("Point", "PointLock", "FloatXY"):
            self.float(v["x"])
            self.float(v["y"])
        elif ptype in ("Degrees", "Float"):
            self.float(v)
        elif ptype in ("Integer", "IntegerLabeled"):
            self.sint(v)
        elif ptype == "FloatVar":
            self.float(v["base"])
            self.float(v["variance"])
        elif ptype == "Check":
            self.bool(v)
        elif ptype == "Byte":
            self.byte(v)
        elif ptype == "Color3":
            for c in v:
                self.byte(c)
        elif ptype == "Color4FVar":
            for c in [*v["base"], *v["variance"]]:
                self.float(c)
        elif ptype == "Flip":
            self.bool(v["x"])
            self.bool(v["y"])
        elif ptype == "Blendmode":
            self.uint(v["src"])
            self.uint(v["dst"])
        elif ptype == "SpriteFrame":
            self.cstr(v["sheet"])
            self.cstr(v["frame"])
        elif ptype == "Animation":
            self.cstr(v["file"])
            self.cstr(v["animation"])
        elif ptype in STRING_TYPES:
            self.cstr(v)
        elif ptype == "Block":
            self.cstr(v["selector"])
            self.uint(_index(TARGETS, v["target"], "target"))
            self.cstr(v["soundFile"])
            self.bool(v["soundEnabled"])
        elif ptype == "BlockCCControl":
            self.cstr(v["selector"])
            self.uint(_index(TARGETS, v["target"], "target"))
            self.uint(v["controlEvents"])
        elif v is not None:                           # NoValue28
            raise ValueError(f"у свойства типа NoValue28 значение должно быть null: {v!r}")

    def body(self, doc: dict) -> None:
        self.sequences(doc)
        self.node(doc["root"])


def build(doc: dict) -> bytes:
    """JSON-документ макета → байты .ccbi."""
    meta: dict[str, Any] = doc.get("ccbi", {})
    version = meta.get("version", CCBI_VERSION)
    if version != CCBI_VERSION:
        raise ValueError(f"версия формата {version}, поддерживается {CCBI_VERSION}")
    js = meta.get("jsControlled", False)
    counter = _Writer(js_controlled=js)               # проход 1: какие строки нужны
    counter.body(doc)
    if "stringCache" in meta:
        cache = list(meta["stringCache"])
        known = set(cache)
        cache += [s for s in counter.used if s not in known]
    else:                                             # как CocosBuilder: частые строки — вперёд
        cache = sorted(counter.used, key=lambda s: -counter.used[s])
    index = {s: i for i, s in enumerate(cache)}
    if len(index) != len(cache):
        raise ValueError("повтор в ccbi.stringCache")
    head = _Writer(js_controlled=js)
    head.out += MAGIC
    head.uint(version)
    head.bool(js)
    head.uint(len(cache))
    for s in cache:
        head.utf8(s)
    body = _Writer(index, js)                         # проход 2: с индексами кэша
    body.body(doc)
    return bytes(head.out + body.out)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="JSON макета (tools/ccbi_to_json.py) → .ccbi")
    ap.add_argument("json", type=Path, help="JSON макета")
    ap.add_argument("ccbi", type=Path, help="куда записать .ccbi")
    args = ap.parse_args(argv)
    data = build(json.loads(args.json.read_text(encoding="utf-8")))
    args.ccbi.write_bytes(data)
    print(f"[ccbi] {args.json} → {args.ccbi} ({len(data)} байт)")


if __name__ == "__main__":
    main()
