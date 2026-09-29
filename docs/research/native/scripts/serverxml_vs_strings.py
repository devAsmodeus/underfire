#!/usr/bin/env python3
"""Tags/attributes of raw/obb_patch/assets/config/server.xml (regex-level) vs libinferno.so strings.
Groups tags by the top-level document (inferno:<section>) they occur in."""
import re, os, collections
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRV = 'raw/obb_patch/assets/config/server.xml'
CFG = 'raw/obb_patch/assets/config/config.xml'
strs = set()
for line in open(os.path.join(BASE, 'cstrings.tsv')):
    a, sec, s = line.rstrip('\n').split('\t', 2)
    if sec in ('.rodata', '.data'): strs.add(s)
def M(s): return 'Y' if s in strs else '-'
def scan(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    docs = re.split(r'<\?xml[^>]*\?>', s)
    per = collections.defaultdict(lambda: [collections.Counter(), collections.Counter()])
    roots = collections.Counter()
    for d in docs:
        m = re.search(r'<([\w:]+)([^>]*)>', d)
        if not m: continue
        root = m.group(1)
        flags = ('client' in m.group(2), 'server' in m.group(2))
        roots[(root, flags)] += 1
        for t, attrs in re.findall(r'<([A-Za-z_][\w:.-]*)((?:\s+[\w:.-]+\s*=\s*"[^"]*")*)\s*/?>', d):
            per[root][0][t] += 1
            for an in re.findall(r'([\w:.-]+)\s*=\s*"', attrs):
                if an.startswith('xmlns'): continue
                per[root][1][t + '@' + an] += 1
    return per, roots
out = []
for path, label in [(SRV, 'server.xml (patch)'), (CFG, 'config.xml (patch)')]:
    per, roots = scan(path)
    out.append(f'\n########## {label}')
    out.append('# root documents (root, has client attr, has server attr): count')
    for (r, fl), n in sorted(roots.items(), key=lambda x: -x[1]):
        out.append(f'   {r:40s} client={int(fl[0])} server={int(fl[1])}  x{n}')
    for root in sorted(per):
        tags, attrs = per[root]
        miss = [t for t in tags if t not in strs and not t.startswith('inferno:')]
        out.append(f'\n=== {root}: tags {len(tags)}, in binary {len(tags)-len(miss)}')
        out.append('  tags: ' + ' '.join(f'{t}[{M(t)}]' for t, _ in tags.most_common()))
        an = collections.Counter()
        for k, v in attrs.items(): an[k.split('@')[1]] += v
        out.append('  attr names: ' + ' '.join(f'{a}[{M(a)}]' for a, _ in an.most_common()))
open(os.path.join(BASE, 'serverxml_names_vs_binary.txt'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(l for l in out if l.startswith('===') or l.startswith('#') or l.startswith('   ')))
