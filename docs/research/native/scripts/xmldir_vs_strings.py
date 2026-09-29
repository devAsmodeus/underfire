#!/usr/bin/env python3
"""Tags/attrs of mission, map, visuals XML files (patch overrides main) vs libinferno.so strings."""
import re, os, collections, glob
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = 'raw'
strs = set()
for line in open(os.path.join(BASE, 'cstrings.tsv')):
    a, sec, s = line.rstrip('\n').split('\t', 2)
    if sec in ('.rodata', '.data'): strs.add(s)
def M(s): return 'Y' if s in strs else '-'
def files(sub):
    d = {}
    for root in ('obb_main', 'obb_patch'):
        for p in glob.glob(f'{RAW}/{root}/assets/config/{sub}/**/*', recursive=True):
            if os.path.isfile(p):
                d[os.path.relpath(p, f'{RAW}/{root}/assets/config/{sub}')] = p
    return d
out = []
for sub in ('missions', 'maps', 'visuals', 'battles', 'actions'):
    fs = files(sub)
    tags = collections.Counter(); attrs = collections.Counter(); vals = collections.defaultdict(collections.Counter)
    for rel, p in fs.items():
        s = open(p, encoding='utf-8', errors='replace').read()
        for t, a in re.findall(r'<([A-Za-z_][\w:.-]*)((?:\s+[\w:.-]+\s*=\s*"[^"]*")*)\s*/?>', s):
            tags[t] += 1
            for an, av in re.findall(r'([\w:.-]+)\s*=\s*"([^"]*)"', a):
                if an.startswith('xmlns'): continue
                attrs[an] += 1
                if len(vals[t + '@' + an]) < 400: vals[t + '@' + an][av] += 1
    miss = [t for t in tags if t not in strs]
    out.append(f'\n=== config/{sub}: files {len(fs)}, distinct tags {len(tags)}, in binary {len(tags)-len(miss)}; attr names {len(attrs)}, in binary {sum(1 for a in attrs if a in strs)}')
    out.append('  tags: ' + ' '.join(f'{t}[{M(t)}]' for t, _ in tags.most_common()))
    out.append('  attrs: ' + ' '.join(f'{a}[{M(a)}]' for a, _ in attrs.most_common()))
    for k, vc in sorted(vals.items()):
        if 1 < len(vc) <= 30 and not all(re.fullmatch(r'-?[0-9.]+', v) for v in vc):
            out.append(f'    enum {k}: ' + ' '.join(f'{v}[{M(v)}]' for v, _ in vc.most_common(30)))
open(os.path.join(BASE, 'xmldirs_names_vs_binary.txt'), 'w').write('\n'.join(out) + '\n')
for l in out:
    if l.startswith('===') or l.startswith('  tags'): print(l[:3000])
