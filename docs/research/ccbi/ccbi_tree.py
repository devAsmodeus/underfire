#!/usr/bin/env python3
"""Читаемое дерево макета: python3 ccbi_tree.py file.ccbi|file.json"""
import json
import sys

import ccbi_parser as P

SKIP = {"ignoreAnchorPointForPosition", "touchEnabled", "mouseEnabled"}


def fmt(p):
    v, t = p["value"], p["type"]
    if t == "Position":
        suf = "" if v["type"] == "RelativeBottomLeft" else f' {v["type"]}'
        return f'pos=({v["x"]:g},{v["y"]:g}){suf}'
    if t == "Size":
        suf = "" if v["type"] == "Absolute" else f' {v["type"]}'
        return f'{p["name"]}=({v["w"]:g}x{v["h"]:g}){suf}'
    if t == "ScaleLock":
        if v["x"] == 1 and v["y"] == 1 and v["type"] == "Absolute":
            return ""
        suf = "" if v["type"] == "Absolute" else "*res"
        return f'scale=({v["x"]:g},{v["y"]:g}){suf}'
    if p["name"] == "anchorPoint":
        return "" if v == [0.5, 0.5] else f"anchor=({v[0]:g},{v[1]:g})"
    if t == "SpriteFrame":
        return f'{p["name"]}={v["frame"]}' if v["frame"] else ""
    if t == "Block":
        s = f'{p["name"]}->{v["selector"]}'
        if v.get("soundFile"):
            s += f' (sound {v["soundFile"]})'
        return s
    if t == "FloatScale":
        return f'{p["name"]}={v["value"]:g}'
    if t == "Text":
        return f'{p["name"]}={json.dumps(v, ensure_ascii=False)}'
    if t == "NoValue28":
        return f'{p["name"]}(28)'
    return f'{p["name"]}={json.dumps(v, ensure_ascii=False)}'


def tree(n, out, ind=0):
    mv = n.get("memberVar")
    head = "  " * ind + n["class"] + (f' «{mv["name"]}»' if mv else "")
    parts = [s for s in (fmt(p) for p in n["props"] if p["name"] not in SKIP) if s]
    if "animated" in n:
        for sid, pp in n["animated"].items():
            for pn, pv in pp.items():
                parts.append(f'ANIM[seq{sid}].{pn}×{len(pv["keyframes"])}')
    out.append(head + "  " + "; ".join(parts))
    for c in n.get("children", []):
        tree(c, out, ind + 1)


def main(path):
    doc = json.load(open(path)) if path.endswith(".json") else P.parse_file(path)
    out = [f'# version={doc["version"]} sequences=' + ", ".join(
        f'{s["name"]}({s["duration"]:g}s{"→" + str(s["chainedSequenceId"]) if s["chainedSequenceId"] != -1 else ""})'
        for s in doc["sequences"]) + f' autoplay={doc["autoPlaySequenceId"]}']
    tree(doc["root"], out)
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
