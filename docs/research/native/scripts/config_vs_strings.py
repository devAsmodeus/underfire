#!/usr/bin/env python3
"""Cross-check names used in data/config.json (tags, attribute names, enum-like values)
against NUL-terminated strings in libinferno.so .rodata. Read-only on the project."""
import json, os, collections, re
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = 'data/config.json'
strs = set()
with open(os.path.join(BASE, 'cstrings.tsv')) as f:
    for line in f:
        a, sec, s = line.rstrip('\n').split('\t', 2)
        if sec in ('.rodata', '.data'):
            strs.add(s)
cfg = json.load(open(CFG))

tags = collections.defaultdict(collections.Counter)        # section -> tag -> count
paths = collections.defaultdict(collections.Counter)       # section -> parent/tag
attrs = collections.defaultdict(collections.Counter)       # section -> tag@attr -> count
attr_vals = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # section -> tag@attr -> value -> n
leaf_vals = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # section -> tag -> text -> n

def walk(sec, n, parent):
    t = n['tag']
    tags[sec][t] += 1
    paths[sec][parent + '/' + t] += 1
    for k, v in n.get('attr', {}).items():
        attrs[sec][t + '@' + k] += 1
        attr_vals[sec][t + '@' + k][v] += 1
    if 'text' in n and 'children' not in n:
        leaf_vals[sec][t][n['text']] += 1
    for c in n.get('children', []):
        walk(sec, c, t)

for sec, ents in cfg.items():
    for e in ents:
        walk(sec, e, sec)

def mark(s):
    return 'Y' if s in strs else '-'

lines = []
summary = []
all_tags = collections.Counter(); all_attrs = collections.Counter()
for sec in sorted(cfg, key=lambda s: -len(cfg[s])):
    lines.append(f'\n=== [{mark(sec)}] section <{sec}> ({len(cfg[sec])} entities)')
    t_hit = sum(1 for t in tags[sec] if t in strs)
    a_names = {k.split('@')[1] for k in attrs[sec]}
    a_hit = sum(1 for a in a_names if a in strs)
    summary.append((sec, len(cfg[sec]), len(tags[sec]), t_hit, len(a_names), a_hit))
    lines.append('  tags: ' + ' '.join(f'{t}[{mark(t)}]' for t, _ in tags[sec].most_common()))
    lines.append('  attrs: ' + ' '.join(f'{k}[{mark(k.split("@")[1])}]' for k, _ in attrs[sec].most_common()))
    # enum-like attr values: attributes with <= 25 distinct values
    for k, vc in attr_vals[sec].items():
        if 1 < len(vc) <= 25 or (len(vc) == 1 and len(k) < 40):
            vals = ' '.join(f'{v}[{mark(v)}]' for v, _ in vc.most_common(25))
            lines.append(f'    enum {k}: {vals}')
    for t, vc in leaf_vals[sec].items():
        nonnum = [v for v in vc if not re.fullmatch(r'-?[0-9.]+', v)]
        if nonnum and len(vc) <= 25:
            vals = ' '.join(f'{v}[{mark(v)}]' for v, _ in vc.most_common(25))
            lines.append(f'    text {t}: {vals}')
    for t in tags[sec]: all_tags[t] += tags[sec][t]
    for k in attrs[sec]: all_attrs[k.split('@')[1]] += attrs[sec][k]

with open(os.path.join(BASE, 'config_names_vs_binary.txt'), 'w') as f:
    f.write('# Names from data/config.json checked against libinferno.so .rodata strings (exact NUL-terminated match)\n')
    f.write('# [Y] = string present in binary, [-] = absent\n')
    f.write('\n# summary: section entities distinct_tags tags_in_binary distinct_attr_names attr_names_in_binary\n')
    for s in summary:
        f.write('%-28s %6d %4d %4d %4d %4d\n' % s)
    f.write('\n'.join(lines))
    missing_t = sorted(t for t in all_tags if t not in strs)
    missing_a = sorted(a for a in all_attrs if a not in strs)
    f.write('\n\n# ALL distinct tags: %d, present: %d\n' % (len(all_tags), len(all_tags) - len(missing_t)))
    f.write('# tags NOT in binary: ' + ' '.join(missing_t) + '\n')
    f.write('# ALL distinct attr names: %d, present: %d\n' % (len(all_attrs), len(all_attrs) - len(missing_a)))
    f.write('# attr names NOT in binary: ' + ' '.join(missing_a) + '\n')
print('sections:', len(summary))
for s in summary: print('%-28s %6d tags %3d/%3d  attrs %3d/%3d' % (s[0], s[1], s[3], s[2], s[5], s[4]))
print('ALL tags', len(all_tags), 'missing', len([t for t in all_tags if t not in strs]))
print('ALL attrs', len(all_attrs), 'missing', len([a for a in all_attrs if a not in strs]))
