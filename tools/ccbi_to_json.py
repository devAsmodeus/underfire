#!/usr/bin/env python3
"""Сбор под браузер: макеты интерфейса CocosBuilder (.ccbi) → JSON для загрузчика UI на PixiJS.

Все 306 файлов макетов (177 путей после перекрытия слоёв) — CCBI v5 в варианте движка Inferno.
От стандарта он отличается двумя вещами: у колбэка (свойство типа Block) после селектора и цели
записаны имя звука и флаг звука, а свойство типа 28 не несёт значения. Разбор без потерь:
tools/ccbi_write.py собирает из JSON исходный файл байт в байт (проверка — --check). Схема ниже,
подробно и со ссылками на cocos2d-x 2.2 — docs/formats/ccbi-json.md, исследование —
docs/research/ccbi.md.

    python3 tools/ccbi_to_json.py            # raw/ → assets/ui/
    python3 tools/ccbi_to_json.py --check    # все файлы всех слоёв: разбор, обратная сборка, классы
Вход  : raw/{apk,obb_main,obb_patch}/assets/interface/**/*.ccbi (patch перекрывает main, main — apk)
Выход : assets/ui/<путь внутри interface/ без .ccbi>.json,
        например assets/ui/1024x768/city/popups/yes_no_popup.json

Схема JSON, formatVersion 1. [ключ] — есть не всегда. Порядок в properties, customProperties,
animatedProperties и children — как в файле (движок применяет свойства по очереди).
  документ     {formatVersion, source: {layer, path}, resolution: {name, width, height} | null,
                sequences: [таймлайн], autoPlaySequenceId (-1 — нет), root: узел,
                ccbi: {version, jsControlled, stringCache}}   — ccbi нужен только обратной сборке
  таймлайн     {sequenceId, name, duration, chainedSequenceId (-1 — нет),
                callbacks: [{time, selector, target}], sounds: [{time, file, pitch, pan, gain}]}
  узел         {baseClass — плагин CocosBuilder, customClass — класс игры поверх него или null,
                memberVarAssignment: {target, name} | null (outlet), [jsController],
                properties: {имя: свойство}, customProperties: {имя: свойство},
                animatedProperties: {"sequenceId": {имя: {type, keyframes: [ключ]}}},
                children: [узел]}
  свойство     {type, value, [positionType | sizeType | scaleType], [platform: "iOS" | "Mac"]}
  ключ         {time, easing, [easingOpt], value}   — value того же вида, что у свойства;
                тип позиции и масштаба для ключей берётся из свойства узла
  value по type: Position, Point, PointLock, FloatXY, ScaleLock → {x, y}; Size → {width, height};
                 Degrees, Float → число; Integer, IntegerLabeled, Byte → целое; Check → bool;
                 FloatScale → число (+ scaleType); FloatVar → {base, variance};
                 Color3 → [r, g, b]; Color4FVar → {base: [r, g, b, a], variance: [r, g, b, a]};
                 Flip → {x, y} из bool; Blendmode → {src, dst} (GLenum);
                 SpriteFrame → {sheet, frame}; Animation → {file, animation};
                 Text, String, FontTTF, FntFile, Texture, CCBFile → строка;
                 Block → {selector, target, soundFile, soundEnabled};
                 BlockCCControl → {selector, target, controlEvents}; NoValue28 → null.
  Перечисления — строками: positionType RelativeBottomLeft | RelativeTopLeft | RelativeTopRight
  | RelativeBottomRight | Percent | MultiplyResolution; sizeType Absolute | Percent
  | RelativeContainer | HorizontalPercent | VerticalPercent | MultiplyResolution;
  scaleType Absolute | MultiplyResolution; target None | DocumentRoot | Owner;
  easing Instant | Linear | CubicIn | … | BackInOut.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ("apk", "obb_main", "obb_patch")           # по возрастанию приоритета
FORMAT_VERSION = 1

MAGIC = b"ibcc"                                     # int 'ccbi', записанный little-endian
CCBI_VERSION = 5

# Типы свойств: индекс — id в файле (kCCBPropType* в CCBReader.h). 28 — расширение Inferno.
PROP_TYPES = (
    "Position", "Size", "Point", "PointLock", "ScaleLock", "Degrees", "Integer", "Float",
    "FloatVar", "Check", "SpriteFrame", "Texture", "Byte", "Color3", "Color4FVar", "Flip",
    "Blendmode", "FntFile", "Text", "FontTTF", "IntegerLabeled", "Block", "Animation", "CCBFile",
    "String", "BlockCCControl", "FloatScale", "FloatXY", "NoValue28",
)
POSITION_TYPES = ("RelativeBottomLeft", "RelativeTopLeft", "RelativeTopRight",
                  "RelativeBottomRight", "Percent", "MultiplyResolution")
SIZE_TYPES = ("Absolute", "Percent", "RelativeContainer", "HorizontalPercent", "VerticalPercent",
              "MultiplyResolution")
SCALE_TYPES = ("Absolute", "MultiplyResolution")
TARGETS = ("None", "DocumentRoot", "Owner")
PLATFORMS = ("All", "iOS", "Mac")
EASINGS = ("Instant", "Linear", "CubicIn", "CubicOut", "CubicInOut", "ElasticIn", "ElasticOut",
           "ElasticInOut", "BounceIn", "BounceOut", "BounceInOut", "BackIn", "BackOut", "BackInOut")
EASINGS_WITH_OPT = frozenset(EASINGS[2:8])          # у Cubic* и Elastic* есть параметр easingOpt
KEYFRAME_TYPES = frozenset(("Check", "Byte", "Color3", "Degrees", "ScaleLock", "Position",
                            "FloatXY", "SpriteFrame"))   # CCBReader::readKeyframe
STRING_TYPES = frozenset(("Texture", "FntFile", "Text", "FontTTF", "CCBFile", "String"))

# В ccbi пишется одно имя класса: customClass, если он задан, иначе baseClass — плагин
# CocosBuilder, который задаёт набор свойств. Эти четыре класса — customClass поверх стандартного
# плагина: свойства у них ровно от плагина; писатель кладёт в кэш строк и baseClass, поэтому
# CCLabelTTF, CCScrollView и CCLayer лежат там без ссылок; customProperties он пишет только при
# customClass (так у CCSpriteBatchNode). Остальные классы — плагины: customClass = null.
CUSTOM_CLASS_BASE = {
    "CCSpriteBatchNode": "CCNode",
    "CCLabelTTFLocalized": "CCLabelTTF",
    "CRjScrollListView": "CCScrollView",
    "MainMenuScene": "CCLayer",
}

# Эталон v1.3.12 — docs/research/ccbi.md (§3.2) и docs/research/ccbi/stats.txt. Сверяет --check.
EXPECTED = {
    "files": {"apk": 2, "obb_main": 161, "obb_patch": 143},
    "effective": {"1024x768": 145, "2048x1536": 32},
    "blocks": 1252, "blocks_with_sound": 1, "novalue28": 20, "novalue28_paths": 4,
    "classes_all": {
        "CCSprite": 4419, "CCNode": 2104, "CCLabelTTF": 1921, "CCMenu": 852, "CCMenuItemImage": 670,
        "CCTextLayout": 434, "CCTextButton": 333, "CCNodeSelector": 159, "CCSpriteBatchNode": 133,
        "CCScrollListView": 90, "CCCheckBox": 90, "CCTableNode": 82, "CCLabelTTFLocalized": 61,
        "CCProgressTimer": 48, "CCLayer": 47, "CCLayerColor": 5, "CCControlButton": 4,
        "CRjScrollListView": 3, "MainMenuScene": 1, "CCScrollView": 1,
    },
    "classes_1024x768": {
        "CCSprite": 2068, "CCNode": 1003, "CCLabelTTF": 890, "CCMenu": 400, "CCMenuItemImage": 297,
        "CCTextLayout": 216, "CCTextButton": 168, "CCNodeSelector": 83, "CCSpriteBatchNode": 57,
        "CCScrollListView": 44, "CCCheckBox": 40, "CCTableNode": 30, "CCProgressTimer": 21,
        "CCLayer": 20, "CCLabelTTFLocalized": 19, "CCLayerColor": 3, "CRjScrollListView": 1,
        "MainMenuScene": 1, "CCScrollView": 1,
    },
}


class CCBIError(ValueError):
    """Файл не укладывается в понятый формат (строгий разбор: ничего не пропускаем молча)."""


def _number(f: float) -> float | int:
    """Целые значения — целыми: в JSON короче, а для загрузчика это одно и то же число."""
    return int(f) if f.is_integer() and abs(f) < 2 ** 53 else f


def _short_f32(raw: bytes) -> float | int:
    """float32 → самая короткая десятичная запись, которая даёт те же 4 байта (без потерь)."""
    (f,) = struct.unpack("<f", raw)
    for digits in range(6, 10):
        cand = float(f"{f:.{digits}g}")
        if struct.pack("<f", cand) == raw:
            return _number(cand)
    return _number(f)


class _Reader:
    """Побитовое чтение CCBI (порт CCBReader.cpp из cocos2d-x 2.2 + расширения Inferno)."""

    def __init__(self, data: bytes, name: str):
        self.data, self.name = data, name
        self.pos = 0
        self.bit = 0
        self.strings: list[str] = []
        self.js_controlled = False

    def fail(self, message: str) -> NoReturn:
        raise CCBIError(f"{self.name}: {message} (байт {self.pos})")

    # ---- базовые типы
    def _need(self, n: int) -> None:
        if self.pos + n > len(self.data):
            self.fail(f"файл кончился, а нужно ещё {n} байт")

    def byte(self) -> int:
        self._need(1)
        self.pos += 1
        return self.data[self.pos - 1]

    def bool(self) -> bool:
        b = self.byte()
        if b > 1:
            self.fail(f"bool = {b}")                  # писатель пишет только 0 и 1
        return b == 1

    def _bit(self) -> int:
        self._need(1)
        value = (self.data[self.pos] >> self.bit) & 1
        self.bit += 1
        if self.bit == 8:
            self.bit, self.pos = 0, self.pos + 1
        return value

    def _gamma(self) -> int:
        """Elias gamma: биты LSB-first, после числа — выравнивание на байт нулями."""
        zeros = 0
        while not self._bit():
            zeros += 1
            if zeros > 32:
                self.fail("целое длиннее 32 бит")
        n = 1
        for _ in range(zeros):
            n = n << 1 | self._bit()
        if self.bit:
            if self.data[self.pos] >> self.bit:
                self.fail("ненулевые биты выравнивания")
            self.bit, self.pos = 0, self.pos + 1
        return n

    def uint(self) -> int:
        return self._gamma() - 1

    def sint(self) -> int:
        n = self._gamma()
        return n // 2 if n % 2 else -(n // 2)

    def float(self) -> float | int:
        kind = self.byte()
        if kind < 4:
            return (0, 1, -1, 0.5)[kind]
        if kind == 4:
            return self.sint()
        if kind == 5:
            self._need(4)
            self.pos += 4
            return _short_f32(self.data[self.pos - 4:self.pos])
        self.fail(f"неизвестный тип float {kind}")

    def utf8(self) -> str:
        self._need(2)
        n = int.from_bytes(self.data[self.pos:self.pos + 2], "big")
        self.pos += 2
        self._need(n)
        self.pos += n
        try:
            return self.data[self.pos - n:self.pos].decode("utf-8")
        except UnicodeDecodeError as e:
            self.fail(f"строка не в UTF-8: {e}")

    def cstr(self) -> str:
        i = self.uint()
        if i >= len(self.strings):
            self.fail(f"индекс строки {i} вне кэша ({len(self.strings)})")
        return self.strings[i]

    def enum(self, table: tuple[str, ...], what: str) -> str:
        i = self.uint()
        if i >= len(table):
            self.fail(f"неизвестный {what}: {i}")
        return table[i]

    # ---- документ
    def document(self) -> dict:
        self._need(4)
        if self.data[:4] != MAGIC:
            self.fail(f"это не ccbi: {self.data[:4]!r}")
        self.pos = 4
        version = self.uint()
        if version != CCBI_VERSION:
            self.fail(f"версия формата {version}, поддерживается {CCBI_VERSION}")
        self.js_controlled = self.bool()
        self.strings = [self.utf8() for _ in range(self.uint())]
        if len(set(self.strings)) != len(self.strings):
            self.fail("повтор в кэше строк — обратная сборка была бы неоднозначной")
        sequences = [self.sequence() for _ in range(self.uint())]
        auto_play = self.sint()
        root = self.node(0)
        if self.pos != len(self.data):
            self.fail(f"лишние байты в конце: {len(self.data) - self.pos}")
        return {"sequences": sequences, "autoPlaySequenceId": auto_play, "root": root,
                "ccbi": {"version": version, "jsControlled": self.js_controlled,
                         "stringCache": self.strings}}

    def sequence(self) -> dict:
        duration, name, seq_id, chained = self.float(), self.cstr(), self.uint(), self.sint()
        callbacks = [{"time": self.float(), "selector": self.cstr(),
                      "target": self.enum(TARGETS, "target")} for _ in range(self.uint())]
        sounds = [{"time": self.float(), "file": self.cstr(), "pitch": self.float(),
                   "pan": self.float(), "gain": self.float()} for _ in range(self.uint())]
        return {"sequenceId": seq_id, "name": name, "duration": duration,
                "chainedSequenceId": chained, "callbacks": callbacks, "sounds": sounds}

    def node(self, depth: int) -> dict:
        if depth > 64:
            self.fail("дерево узлов глубже 64")
        cls = self.cstr()
        base = CUSTOM_CLASS_BASE.get(cls)
        node: dict[str, Any] = {"baseClass": base or cls, "customClass": cls if base else None}
        if self.js_controlled:
            node["jsController"] = self.cstr()
        target = self.enum(TARGETS, "target")
        node["memberVarAssignment"] = (None if target == "None"
                                       else {"target": target, "name": self.cstr()})
        animated: dict[str, dict] = {}
        for _ in range(self.uint()):
            seq_id = str(self.uint())
            if seq_id in animated:
                self.fail(f"таймлайн {seq_id} у узла повторяется")
            tracks: dict[str, dict] = {}
            for _ in range(self.uint()):
                name = self.cstr()
                ptype = self.enum(PROP_TYPES, "тип свойства")
                if ptype not in KEYFRAME_TYPES:
                    self.fail(f"тип {ptype} не анимируется ({name})")
                if name in tracks:
                    self.fail(f"анимация свойства {name} повторяется")
                tracks[name] = {"type": ptype,
                                "keyframes": [self.keyframe(ptype) for _ in range(self.uint())]}
            animated[seq_id] = tracks
        properties: dict[str, dict] = {}
        custom: dict[str, dict] = {}
        regular = self.uint()
        for i in range(regular + self.uint()):
            ptype = self.enum(PROP_TYPES, "тип свойства")
            name = self.cstr()
            platform = self.byte()
            if platform >= len(PLATFORMS):
                self.fail(f"неизвестная платформа {platform} ({name})")
            prop = self.prop(ptype)
            if platform:
                prop["platform"] = PLATFORMS[platform]
            bucket = properties if i < regular else custom
            if name in bucket:
                self.fail(f"свойство {name} повторяется")
            bucket[name] = prop
        node["properties"] = properties
        node["customProperties"] = custom
        node["animatedProperties"] = animated
        node["children"] = [self.node(depth + 1) for _ in range(self.uint())]
        return node

    def keyframe(self, ptype: str) -> dict:
        kf: dict[str, Any] = {"time": self.float(), "easing": self.enum(EASINGS, "easing")}
        if kf["easing"] in EASINGS_WITH_OPT:
            kf["easingOpt"] = self.float()
        if ptype == "Check":
            kf["value"] = self.bool()
        elif ptype == "Byte":
            kf["value"] = self.byte()
        elif ptype == "Color3":
            kf["value"] = [self.byte(), self.byte(), self.byte()]
        elif ptype == "Degrees":
            kf["value"] = self.float()
        elif ptype == "SpriteFrame":
            kf["value"] = {"sheet": self.cstr(), "frame": self.cstr()}
        else:                                         # ScaleLock, Position, FloatXY
            kf["value"] = {"x": self.float(), "y": self.float()}
        return kf

    def prop(self, ptype: str) -> dict:
        """Значение свойства (CCNodeLoader::parsePropType*); Block и 28 — как в движке Inferno."""
        p: dict[str, Any] = {"type": ptype}
        if ptype == "Position":
            p["value"] = {"x": self.float(), "y": self.float()}
            p["positionType"] = self.enum(POSITION_TYPES, "positionType")
        elif ptype == "Size":
            p["value"] = {"width": self.float(), "height": self.float()}
            p["sizeType"] = self.enum(SIZE_TYPES, "sizeType")
        elif ptype == "ScaleLock":
            p["value"] = {"x": self.float(), "y": self.float()}
            p["scaleType"] = self.enum(SCALE_TYPES, "scaleType")
        elif ptype == "FloatScale":
            p["value"] = self.float()
            p["scaleType"] = self.enum(SCALE_TYPES, "scaleType")
        elif ptype in ("Point", "PointLock", "FloatXY"):
            p["value"] = {"x": self.float(), "y": self.float()}
        elif ptype in ("Degrees", "Float"):
            p["value"] = self.float()
        elif ptype in ("Integer", "IntegerLabeled"):
            p["value"] = self.sint()
        elif ptype == "FloatVar":
            p["value"] = {"base": self.float(), "variance": self.float()}
        elif ptype == "Check":
            p["value"] = self.bool()
        elif ptype == "Byte":
            p["value"] = self.byte()
        elif ptype == "Color3":
            p["value"] = [self.byte(), self.byte(), self.byte()]
        elif ptype == "Color4FVar":
            p["value"] = {"base": [self.float() for _ in range(4)],
                          "variance": [self.float() for _ in range(4)]}
        elif ptype == "Flip":
            p["value"] = {"x": self.bool(), "y": self.bool()}
        elif ptype == "Blendmode":
            p["value"] = {"src": self.uint(), "dst": self.uint()}
        elif ptype == "SpriteFrame":
            p["value"] = {"sheet": self.cstr(), "frame": self.cstr()}
        elif ptype == "Animation":
            p["value"] = {"file": self.cstr(), "animation": self.cstr()}
        elif ptype in STRING_TYPES:
            p["value"] = self.cstr()
        elif ptype == "Block":                        # Inferno: + soundFile, soundEnabled
            p["value"] = {"selector": self.cstr(), "target": self.enum(TARGETS, "target"),
                          "soundFile": self.cstr(), "soundEnabled": self.bool()}
        elif ptype == "BlockCCControl":
            p["value"] = {"selector": self.cstr(), "target": self.enum(TARGETS, "target"),
                          "controlEvents": self.uint()}
        else:                                         # NoValue28: в движке — пустой case
            p["value"] = None
        return p


def parse(data: bytes, name: str = "ccbi") -> dict:
    """Байты .ccbi → {sequences, autoPlaySequenceId, root, ccbi}; при ошибке формата — CCBIError."""
    return _Reader(data, name).document()


def resolution(rel: str) -> dict | None:
    """Метаданные разрешения по первой папке пути: 1024x768/city/… → 1024×768."""
    m = re.fullmatch(r"(\d+)x(\d+)", rel.split("/", 1)[0])
    return {"name": m[0], "width": int(m[1]), "height": int(m[2])} if m else None


def layout(data: bytes, rel: str, layer: str | None = None) -> dict:
    """Полный JSON-документ макета: метаданные + разбор."""
    return {"formatVersion": FORMAT_VERSION, "source": {"layer": layer, "path": rel},
            "resolution": resolution(rel), **parse(data, rel)}


def dumps(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False) + "\n"


def walk(node: dict) -> Iterator[dict]:
    """Узел и все его потомки, в порядке файла."""
    yield node
    for child in node["children"]:
        yield from walk(child)


def class_name(node: dict) -> str:
    """Имя класса, как оно записано в ccbi (по нему движок выбирает загрузчик)."""
    return node["customClass"] or node["baseClass"]


def find_layouts(raw: Path) -> list[tuple[str, str, Path]]:
    """Все .ccbi всех слоёв: (слой, путь внутри interface/, файл), младший слой — первым."""
    found = []
    for layer in LAYERS:
        base = raw / layer / "assets" / "interface"
        for path in sorted(base.rglob("*.ccbi")):
            found.append((layer, path.relative_to(base).as_posix(), path))
    return found


def effective(found: list[tuple[str, str, Path]]) -> dict[str, tuple[str, Path]]:
    """Путь → (слой, файл) с перекрытием: patch > main > apk."""
    eff: dict[str, tuple[str, Path]] = {}
    for layer, rel, path in found:
        eff[rel] = (layer, path)
    return dict(sorted(eff.items()))


def convert(raw: Path, out: Path) -> dict[str, dict]:
    """Эффективный набор макетов → out/<путь без .ccbi>.json. Возвращает документы по путям."""
    docs = {}
    for rel, (layer, path) in effective(find_layouts(raw)).items():
        doc = layout(path.read_bytes(), rel, layer)
        dst = out / (rel.removesuffix(".ccbi") + ".json")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(dumps(doc), encoding="utf-8")
        docs[rel] = doc
    return docs


def _classes(docs: list[dict]) -> Counter:
    return Counter(class_name(n) for doc in docs for n in walk(doc["root"]))


def _fmt(counter: Counter | dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def check(raw: Path) -> list[str]:
    """Все .ccbi всех слоёв: строгий разбор, JSON → .ccbi байт в байт, сверка с эталоном отчёта.

    Печатает сводку; возвращает список расхождений (пустой — всё сошлось).
    """
    import ccbi_write  # писатель берёт таблицы формата отсюда, поэтому импорт — здесь, без цикла

    problems: list[str] = []
    found = find_layouts(raw)
    per_layer = Counter(layer for layer, _, _ in found)
    docs: dict[tuple[str, str], dict] = {}
    exact = 0
    for layer, rel, path in found:
        data = path.read_bytes()
        try:
            doc = layout(data, rel, layer)
        except CCBIError as e:
            problems.append(f"не разобран: {e}")
            continue
        docs[layer, rel] = doc
        if ccbi_write.build(json.loads(dumps(doc))) == data:
            exact += 1
        else:
            problems.append(f"обратная сборка не совпала: {layer}/{rel}")
    print(f"[ccbi] файлов: {len(found)} ({_fmt(per_layer)}); разобрано: {len(docs)}; "
          f"JSON → .ccbi байт в байт: {exact}")
    if dict(per_layer) != EXPECTED["files"]:
        problems.append(f"файлов по слоям {dict(per_layer)}, в отчёте {EXPECTED['files']}")

    blocks = [p["value"] for doc in docs.values() for n in walk(doc["root"])
              for p in n["properties"].values() if p["type"] == "Block"]
    sounds = Counter(b["soundFile"] for b in blocks if b["soundFile"] or b["soundEnabled"])
    novalue = Counter(key for key, doc in docs.items() for n in walk(doc["root"])
                      for p in n["properties"].values() if p["type"] == "NoValue28")
    novalue_paths = {rel for _, rel in novalue}
    print(f"[ccbi] вариант Inferno: Block {len(blocks)}, со звуком {sum(sounds.values())} "
          f"({_fmt(sounds) or '—'}); тип 28: {sum(novalue.values())} в {len(novalue)} файлах "
          f"({len(novalue_paths)} путях)")
    got = {"blocks": len(blocks), "blocks_with_sound": sum(sounds.values()),
           "novalue28": sum(novalue.values()), "novalue28_paths": len(novalue_paths)}
    for key, value in got.items():
        if value != EXPECTED[key]:
            problems.append(f"{key}: {value}, в отчёте {EXPECTED[key]}")

    eff = effective(found)
    by_res = Counter(rel.split("/", 1)[0] for rel in eff)
    print(f"[ccbi] эффективный набор: {len(eff)} ({_fmt(by_res)})")
    if dict(by_res) != EXPECTED["effective"]:
        problems.append(f"эффективный набор {dict(by_res)}, в отчёте {EXPECTED['effective']}")
    slices = {
        "classes_all": ("все файлы", list(docs.values())),
        "classes_1024x768": ("эффективный набор 1024x768",
                             [docs[layer, rel] for rel, (layer, _) in eff.items()
                              if rel.startswith("1024x768/") and (layer, rel) in docs]),
    }
    for key, (title, subset) in slices.items():
        classes = _classes(subset)
        same = dict(classes) == EXPECTED[key]
        print(f"[ccbi] классы, {title} ({len(subset)} файлов, {sum(classes.values())} узлов): "
              f"{_fmt(classes)} — {'совпало с отчётом' if same else 'НЕ совпало с отчётом'}")
        if not same:
            problems.append(f"{key}: {dict(classes)}, в отчёте {EXPECTED[key]}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Макеты .ccbi (Inferno) → JSON для загрузчика UI")
    ap.add_argument("--raw", type=Path, default=ROOT / "raw",
                    help="распакованный оригинал (по умолчанию raw/)")
    ap.add_argument("--out", type=Path, default=ROOT / "assets" / "ui",
                    help="куда писать JSON (по умолчанию assets/ui/)")
    ap.add_argument("--check", action="store_true",
                    help="проверить все файлы всех слоёв вместо конвертации")
    args = ap.parse_args(argv)
    if not find_layouts(args.raw):
        raise SystemExit(f"в {args.raw}/*/assets/interface/ нет .ccbi — сначала "
                         "tools/extract_xapk.py (README → «Подготовка данных»)")
    if args.check:
        problems = check(args.raw)
        for p in problems:
            print(f"[!] {p}")
        return 1 if problems else 0
    docs = convert(args.raw, args.out)
    by_res = Counter(rel.split("/", 1)[0] for rel in docs)
    print(f"[ccbi] макетов: {len(docs)} ({_fmt(by_res)}) → {args.out}")
    for res in sorted(by_res):
        classes = _classes([d for rel, d in docs.items() if rel.startswith(res + "/")])
        print(f"[ccbi] {res}: узлов {sum(classes.values())}; {_fmt(classes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
