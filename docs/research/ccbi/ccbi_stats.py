#!/usr/bin/env python3
"""
Прогон ccbi_parser по всем .ccbi из raw/ и сбор статистики.

Выход (в папку скрипта):
  json_all/<rel>.json  — разбор каждого «эффективного» макета (patch > main > apk)
  stats.json           — машинная статистика
  stats.txt            — читаемая сводка

Только чтение из raw/ и из libinferno.so-строк (bin/strings.txt, если есть).
"""
from __future__ import annotations

import collections
import glob
import hashlib
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ccbi_parser as P  # noqa: E402

RAW = "raw"
SOURCES = ["apk", "obb_main", "obb_patch"]  # по возрастанию приоритета
RES = "1024x768"  # единственное разрешение в interface.xml

C = collections.Counter
DD = collections.defaultdict


def sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()


# ------------------------------------------------------------------ файлы
def collect():
    all_files = []  # (src, rel, path)
    for src in SOURCES:
        for f in sorted(glob.glob(f"{RAW}/{src}/assets/interface/**/*.ccbi", recursive=True)):
            rel = f.split("/assets/interface/", 1)[1]
            all_files.append((src, rel, f))
    eff = {}
    for src, rel, f in all_files:
        eff[rel] = (src, f)  # поздний источник перекрывает ранний
    return all_files, eff


# ------------------------------------------------------------------ атласы
def atlas_index():
    """frame name -> [atlas rel path] для textures_etc/interface/<RES> (patch > main)."""
    atl = {}
    for src in ["obb_main", "obb_patch"]:
        for f in glob.glob(f"{RAW}/{src}/assets/textures_etc/interface/{RES}/**/*.atlas", recursive=True):
            rel = f.split(f"/textures_etc/interface/{RES}/", 1)[1]
            atl[rel] = f
    frames = DD(list)
    rotated = 0
    total = 0
    for rel, f in sorted(atl.items()):
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line or line.startswith("textures:"):
                    continue
                parts = line.split("\t")
                name = parts[0].lstrip("/")
                frames[name].append(rel[:-len(".atlas")])
                total += 1
                if len(parts) > 9 and parts[9].strip() == "r":
                    rotated += 1
    return atl, frames, total, rotated


def other_images():
    """Имя файла -> пути для icons/**.png и прочих png в obb/apk (запасной поиск)."""
    idx = DD(list)
    for src in SOURCES:
        for f in glob.glob(f"{RAW}/{src}/assets/**/*.png", recursive=True):
            idx[os.path.basename(f)].append(f.split("/assets/", 1)[1])
    return idx


def other_atlas_frames():
    """Кадры из НЕинтерфейсных атласов (icons, buildings...) — на случай ссылок туда."""
    idx = DD(set)
    for src in ["obb_main", "obb_patch"]:
        for f in glob.glob(f"{RAW}/{src}/assets/textures_etc/**/*.atlas", recursive=True):
            if "/textures_etc/interface/" in f:
                continue
            rel = f.split("/textures_etc/", 1)[1]
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("textures:") or not line.strip():
                        continue
                    idx[line.split("\t")[0].lstrip("/")].add(rel)
    return idx


# ------------------------------------------------------------------ обход
def walk(node, depth=0, parent=None):
    yield node, depth, parent
    for ch in node.get("children", []):
        yield from walk(ch, depth + 1, node)


def prop(node, name):
    for p in node["props"]:
        if p["name"] == name:
            return p["value"]
    return None


def binary_ccbi_refs():
    path = os.path.join(HERE, "bin", "strings.txt")
    if not os.path.exists(path):
        return None
    refs = set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for m in re.findall(r"[A-Za-z0-9_/]+\.ccbi", line):
                refs.add(m)
    return refs


def resolve_ccbi(name: str, eff_names: dict, base_dir: str | None = None):
    """Имя из кода/шаблона (с .ccbi или без, возможно с подпапкой) -> список rel в RES.

    Движок грузит макет относительно папки сцены (interface/%definition%/<scene>/),
    поэтому берём все файлы, чей путь оканчивается на "/<name>.ccbi" (верхняя оценка).
    """
    n = name[:-5] if name.endswith(".ccbi") else name
    suffix = "/" + n.lstrip("/") + ".ccbi"
    return sorted(k for k in eff_names if k.startswith(RES + "/") and k.endswith(suffix)) or None


# ------------------------------------------------------------------ main
def main():
    all_files, eff = collect()
    parsed = {}
    fails = []
    for src, rel, f in all_files:
        try:
            parsed[(src, rel)] = P.parse_file(f)
        except Exception as e:  # noqa: BLE001
            fails.append((src, rel, str(e)))
    vanilla_fail = 0
    for src, rel, f in all_files:
        try:
            P.parse_file(f, "vanilla")
        except Exception:  # noqa: BLE001
            vanilla_fail += 1

    # дубликаты main/patch
    by_rel = DD(list)
    for src, rel, f in all_files:
        by_rel[rel].append((src, sha(f)))
    overridden = {rel: v for rel, v in by_rel.items() if len(v) > 1}
    overridden_same = sum(1 for v in overridden.values() if len({h for _, h in v}) == 1)

    # выгрузка JSON эффективного набора
    out_dir = os.path.join(HERE, "json_all")
    for rel, (src, f) in eff.items():
        doc = parsed[(src, rel)]
        dst = os.path.join(out_dir, rel[:-5] + ".json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            json.dump({"source": f"{src}/assets/interface/{rel}", **doc}, fh, ensure_ascii=False, indent=1)

    eff_res = {rel: v for rel, v in eff.items() if rel.startswith(RES + "/")}
    eff_docs = {rel: parsed[(src, rel)] for rel, (src, f) in eff_res.items()}

    # ---------- живые макеты: ссылки из бинарника + шаблоны/контейнеры транзитивно
    bin_refs = binary_ccbi_refs()
    live = set()
    unresolved_bin = []
    if bin_refs is not None:
        for r in sorted(bin_refs):
            if r == ".ccbi":
                continue
            hit = resolve_ccbi(r, eff_res)
            if isinstance(hit, str):
                live.add(hit)
            elif isinstance(hit, list):
                live.update(hit)
            else:
                unresolved_bin.append(r)
        frontier = list(live)
        while frontier:
            rel = frontier.pop()
            doc = eff_docs[rel]
            for n, _, _ in walk(doc["root"]):
                for p in n["props"]:
                    if p["name"] in ("_template", "template") and p["value"]:
                        hit = resolve_ccbi(p["value"], eff_res, os.path.dirname(rel)[len(RES) + 1:])
                        for h in ([hit] if isinstance(hit, str) else (hit or [])):
                            if h not in live:
                                live.add(h)
                                frontier.append(h)
                    if p["type"] == "CCBFile" and p["value"]:
                        hit = resolve_ccbi(p["value"], eff_res)
                        for h in ([hit] if isinstance(hit, str) else (hit or [])):
                            if h not in live:
                                live.add(h)
                                frontier.append(h)

    # ---------- статистика по набору
    def analyze(docs: dict):
        s = {}
        cls_n, cls_files = C(), DD(set)
        props = DD(C)
        custom_props = DD(C)
        pos_types, size_types, scale_types, fscale_types = C(), C(), C(), C()
        anchor = C()
        ignore_anchor_true = C()
        vis_false = C()
        rot_nonzero = 0
        skew = 0
        opacity_non255 = 0
        colored = 0
        blend = C()
        blocks = C()
        block_targets = C()
        block_sounds = C()
        block_ctrl = 0
        member_targets = C()
        member_names = set()
        frames = C()
        frame_sheets = C()
        fonts = C()
        font_sizes = C()
        texts = C()
        text_classes = C()
        label_dims = C()
        halign, valign = C(), C()
        templates = C()
        ccbfiles = C()
        batch_textures = C()
        nodes_per_file = []
        depth_max = []
        seq_files = 0
        seq_total = 0
        seq_names = C()
        seq_nontrivial_files = []
        anim_nodes = 0
        anim_props = C()
        anim_kf = 0
        easing = C()
        callbacks = 0
        sounds = 0
        chained = 0
        autoplay = C()
        progress_types = C()
        nodes_total = 0
        root_classes = C()
        root_size = C()
        for rel, doc in docs.items():
            root_classes[doc["root"]["class"]] += 1
            cs = prop(doc["root"], "contentSize")
            if cs:
                root_size[f'{cs["w"]:g}x{cs["h"]:g} {cs["type"]}'] += 1
            n_nodes = 0
            dmax = 0
            has_anim = False
            for n, depth, parent in walk(doc["root"]):
                n_nodes += 1
                dmax = max(dmax, depth)
                c = n["class"]
                cls_n[c] += 1
                cls_files[c].add(rel)
                if "memberVar" in n:
                    member_targets[n["memberVar"]["target"]] += 1
                    member_names.add(n["memberVar"]["name"])
                if "animated" in n:
                    has_anim = True
                    anim_nodes += 1
                    for sid, pp in n["animated"].items():
                        for pn, pv in pp.items():
                            anim_props[f'{pn}:{pv["type"]}'] += 1
                            for kf in pv["keyframes"]:
                                anim_kf += 1
                                easing[kf["easing"]] += 1
                for p in n["props"]:
                    key = (p["name"], p["type"])
                    (custom_props if p.get("custom") else props)[c][f"{p['name']}:{p['type']}"] += 1
                    v = p["value"]
                    t = p["type"]
                    if t == "Position":
                        pos_types[v["type"]] += 1
                    elif t == "Size":
                        size_types[f'{p["name"]}:{v["type"]}'] += 1
                        if p["name"] == "dimensions":
                            label_dims["0x0" if (v["w"] == 0 and v["h"] == 0) else "set"] += 1
                    elif t == "ScaleLock":
                        scale_types[v["type"]] += 1
                    elif t == "FloatScale":
                        fscale_types[v["type"]] += 1
                        if "FontSize" in p["name"] or p["name"] == "fontSize":
                            font_sizes[v["value"]] += 1
                    if p["name"] == "anchorPoint":
                        anchor[f"({v[0]:g},{v[1]:g})"] += 1
                    if p["name"] == "ignoreAnchorPointForPosition" and v:
                        ignore_anchor_true[c] += 1
                    if p["name"] == "visible" and v is False:
                        vis_false[c] += 1
                    if p["name"] == "rotation" and v:
                        rot_nonzero += 1
                    if p["name"] in ("skew", "skewX", "skewY") and v:
                        skew += 1
                    if p["name"] == "opacity" and v != 255:
                        opacity_non255 += 1
                    if p["name"] == "color" and v != [255, 255, 255]:
                        colored += 1
                    if t == "Blendmode":
                        blend[f'{v["src"]}/{v["dst"]}'] += 1
                    if t == "Block":
                        blocks[v["selector"]] += 1
                        block_targets[v["target"]] += 1
                        if v.get("soundFile"):
                            block_sounds[v["soundFile"]] += 1
                    if t == "BlockCCControl":
                        block_ctrl += 1
                    if t == "SpriteFrame":
                        if v["frame"]:
                            frames[v["frame"]] += 1
                            frame_sheets["(empty)" if not v["sheet"] else v["sheet"]] += 1
                    if t == "FontTTF":
                        fonts[v] += 1
                    if t == "Text":
                        texts[v] += 1
                        text_classes[c] += 1
                    if p["name"] in ("horizontalAlignment", "horizTextAlignment", "textAlignment",
                                     "normalHorizontalAlignment"):
                        halign[f"{p['name']}={v}"] += 1
                    if p["name"] in ("verticalAlignment", "verticalTextAlignment", "normalVerticalAlignment"):
                        valign[f"{p['name']}={v}"] += 1
                    if p["name"] in ("_template", "template"):
                        templates[v] += 1
                    if t == "CCBFile":
                        ccbfiles[v] += 1
                    if c == "CCSpriteBatchNode" and p["name"] in ("texture", "textures"):
                        batch_textures[v] += 1
                    if c == "CCProgressTimer" and p["name"] == "type":
                        progress_types[v] += 1
            nodes_total += n_nodes
            nodes_per_file.append(n_nodes)
            depth_max.append(dmax)
            seqs = doc["sequences"]
            seq_total += len(seqs)
            if seqs:
                seq_files += 1
            for sq in seqs:
                seq_names[sq["name"]] += 1
                callbacks += len(sq.get("callbacks", []))
                sounds += len(sq.get("sounds", []))
                if sq["chainedSequenceId"] != -1:
                    chained += 1
            autoplay["none" if doc["autoPlaySequenceId"] == -1 else "set"] += 1
            if has_anim or len(seqs) > 1:
                seq_nontrivial_files.append(rel)
        s["files"] = len(docs)
        s["nodes_total"] = nodes_total
        s["nodes_per_file"] = {"min": min(nodes_per_file), "median": statistics.median(nodes_per_file),
                               "max": max(nodes_per_file)}
        s["depth_max"] = {"median": statistics.median(depth_max), "max": max(depth_max)}
        s["root_classes"] = dict(root_classes.most_common())
        s["root_contentSize"] = dict(root_size.most_common())
        s["classes"] = {c: {"nodes": n, "files": len(cls_files[c])} for c, n in cls_n.most_common()}
        s["props_by_class"] = {c: dict(v.most_common()) for c, v in props.items()}
        s["custom_props_by_class"] = {c: dict(v.most_common()) for c, v in custom_props.items()}
        s["position_types"] = dict(pos_types.most_common())
        s["size_types"] = dict(size_types.most_common())
        s["scale_types"] = dict(scale_types.most_common())
        s["floatscale_types"] = dict(fscale_types.most_common())
        s["anchorPoint"] = dict(anchor.most_common(12))
        s["ignoreAnchorPointForPosition_true_by_class"] = dict(ignore_anchor_true.most_common())
        s["visible_false_by_class"] = dict(vis_false.most_common())
        s["rotation_nonzero"] = rot_nonzero
        s["skew_nonzero"] = skew
        s["opacity_non255"] = opacity_non255
        s["color_non_white"] = colored
        s["blendFunc"] = dict(blend.most_common())
        s["blocks"] = {"total": sum(blocks.values()), "unique_selectors": len(blocks),
                       "targets": dict(block_targets), "with_sound": dict(block_sounds),
                       "top": dict(blocks.most_common(25))}
        s["blockCCControl"] = block_ctrl
        s["memberVars"] = {"total": sum(member_targets.values()), "targets": dict(member_targets),
                           "unique_names": len(member_names)}
        s["sprite_frames"] = {"refs": sum(frames.values()), "unique": len(frames),
                              "sheets": dict(frame_sheets.most_common())}
        s["_frames_counter"] = frames
        s["fonts"] = dict(fonts.most_common())
        s["font_sizes"] = dict(sorted(font_sizes.items()))
        s["texts"] = {"total": sum(texts.values()), "unique": len(texts),
                      "by_class": dict(text_classes.most_common()),
                      "cyrillic_unique": sum(1 for t in texts if re.search("[А-Яа-яЁё]", t)),
                      "placeholder_like": sum(n for t, n in texts.items()
                                              if t in ("Sample Text", "", "test") or re.fullmatch(r"[\d\s+\-/:%.,]+", t)),
                      "top": dict(texts.most_common(20))}
        s["label_dimensions"] = dict(label_dims)
        s["h_alignment"] = dict(halign.most_common())
        s["v_alignment"] = dict(valign.most_common())
        s["list_templates"] = dict(templates.most_common())
        s["ccbfile_props"] = dict(ccbfiles.most_common())
        s["batch_textures"] = dict(batch_textures.most_common())
        s["progress_timer_types"] = dict(progress_types)
        s["animation"] = {
            "files_with_sequences": seq_files, "sequences_total": seq_total,
            "sequence_names_top": dict(seq_names.most_common(15)),
            "files_with_keyframes_or_multi_seq": len(seq_nontrivial_files),
            "files_list": sorted(seq_nontrivial_files),
            "animated_nodes": anim_nodes, "animated_props": dict(anim_props.most_common()),
            "keyframes": anim_kf, "easing": dict(easing.most_common()),
            "callback_keyframes": callbacks, "sound_keyframes": sounds,
            "chained_sequences": chained, "autoplay": dict(autoplay),
        }
        return s

    st_eff = analyze(eff_docs)
    st_live = analyze({k: v for k, v in eff_docs.items() if k in live}) if live else None
    st_all = analyze({f"{src}:{rel}": d for (src, rel), d in parsed.items()})

    # ---------- ресурсы: кадры против атласов
    atl, frame_idx, frames_total, frames_rot = atlas_index()
    img_idx = other_images()
    other_fr = other_atlas_frames()
    frames = st_eff.pop("_frames_counter")
    st_live and st_live.pop("_frames_counter")
    st_all.pop("_frames_counter")
    found_atlas, found_other_atlas, found_png, missing = {}, {}, {}, {}
    for fr, n in frames.items():
        base = fr.lstrip("/")
        if base in frame_idx:
            found_atlas[fr] = frame_idx[base]
        elif base in other_fr:
            found_other_atlas[fr] = sorted(other_fr[base])
        elif os.path.basename(base) in img_idx:
            found_png[fr] = img_idx[os.path.basename(base)]
        else:
            missing[fr] = n
    multi_atlas = {k: v for k, v in found_atlas.items() if len(set(v)) > 1}
    resources = {
        "interface_atlases": len(atl), "interface_atlas_frames": frames_total,
        "interface_atlas_frames_rotated": frames_rot,
        "unique_frames_referenced": len(frames),
        "found_in_interface_atlases": len(found_atlas),
        "found_in_other_atlases": len(found_other_atlas),
        "found_as_png_file": len(found_png),
        "missing": len(missing),
        "missing_list": dict(sorted(missing.items(), key=lambda x: -x[1])),
        "found_in_other_atlases_list": found_other_atlas,
        "found_as_png_list": {k: v[:3] for k, v in found_png.items()},
        "frames_in_several_atlases": len(multi_atlas),
        "fonts_dir": sorted(os.listdir(f"{RAW}/apk/assets/fonts")),
    }

    summary = {
        "files_total": len(all_files),
        "by_source": dict(C(src for src, _, _ in all_files)),
        "by_resolution": dict(C(rel.split("/")[0] for _, rel, _ in all_files)),
        "effective_unique": len(eff),
        "effective_by_resolution": dict(C(rel.split("/")[0] for rel in eff)),
        "overridden_paths": len(overridden),
        "overridden_identical_bytes": overridden_same,
        "parse_fail_inferno_dialect": fails,
        "parse_fail_vanilla_dialect": vanilla_fail,
        "versions": dict(C(d["version"] for d in parsed.values())),
        "jsControlled": dict(C(str(d["jsControlled"]) for d in parsed.values())),
        "binary_ccbi_refs": None if bin_refs is None else len(bin_refs - {".ccbi"}),
        "binary_refs_unresolved": unresolved_bin,
        "live_files": len(live),
        "dead_files": sorted(set(eff_res) - live) if live else None,
    }
    stats = {"summary": summary, "effective_1024x768": st_eff, "live_1024x768": st_live,
             "all_306_files": st_all, "resources": resources}
    with open(os.path.join(HERE, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=1, default=str)
    write_txt(stats)
    print(json.dumps(summary, ensure_ascii=False, indent=1, default=str)[:3000])


def write_txt(stats):
    L = []
    s = stats["summary"]
    L.append("== ФАЙЛЫ")
    for k in ("files_total", "by_source", "by_resolution", "effective_unique", "effective_by_resolution",
              "overridden_paths", "overridden_identical_bytes", "versions", "jsControlled",
              "parse_fail_vanilla_dialect", "binary_ccbi_refs", "live_files"):
        L.append(f"{k}: {s[k]}")
    L.append(f"parse_fail_inferno_dialect: {len(s['parse_fail_inferno_dialect'])}")
    L.append(f"binary_refs_unresolved: {s['binary_refs_unresolved']}")
    L.append(f"dead_files ({len(s['dead_files'] or [])}): {s['dead_files']}")
    for key, title in (("effective_1024x768", "ЭФФЕКТИВНЫЙ НАБОР 1024x768"), ("live_1024x768", "ЖИВЫЕ МАКЕТЫ 1024x768"),
                       ("all_306_files", "ВСЕ 306 ФАЙЛОВ")):
        st = stats[key]
        if not st:
            continue
        L.append("")
        L.append(f"== {title}: файлов {st['files']}, нод {st['nodes_total']}, "
                 f"нод/файл {st['nodes_per_file']}, глубина {st['depth_max']}")
        L.append("-- классы (ноды / файлы):")
        for c, v in st["classes"].items():
            L.append(f"   {v['nodes']:6d} {v['files']:4d}  {c}")
        if key == "all_306_files":
            continue
        for k in ("root_classes", "root_contentSize", "position_types", "size_types", "scale_types",
                  "floatscale_types", "anchorPoint", "ignoreAnchorPointForPosition_true_by_class",
                  "visible_false_by_class", "rotation_nonzero", "skew_nonzero", "opacity_non255",
                  "color_non_white", "blendFunc", "blocks", "blockCCControl", "memberVars", "sprite_frames",
                  "fonts", "font_sizes", "texts", "label_dimensions", "h_alignment", "v_alignment",
                  "list_templates", "ccbfile_props", "batch_textures", "progress_timer_types", "animation"):
            L.append(f"-- {k}: {json.dumps(st[k], ensure_ascii=False, default=str)}")
        L.append("-- свойства по классам:")
        for c, pp in st["props_by_class"].items():
            L.append(f"   {c}: {json.dumps(pp, ensure_ascii=False)}")
        L.append("-- extra (custom) свойства по классам:")
        for c, pp in st["custom_props_by_class"].items():
            L.append(f"   {c}: {json.dumps(pp, ensure_ascii=False)}")
    L.append("")
    L.append("== РЕСУРСЫ")
    for k, v in stats["resources"].items():
        L.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    with open(os.path.join(HERE, "stats.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
