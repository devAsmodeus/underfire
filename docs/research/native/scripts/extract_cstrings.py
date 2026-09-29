#!/usr/bin/env python3
"""Extract all NUL-terminated printable ASCII/UTF-8 strings (len>=1) from .rodata/.data/.data.rel.ro of libinferno.so
with their virtual addresses. Output: cstrings.tsv (vaddr, section, string)."""
import struct, os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = open(os.path.join(BASE, 'bin/libinferno.so'), 'rb').read()
# parse ELF32 section headers
e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', data, 0x2e)
secs = []
for i in range(e_shnum):
    sh = struct.unpack_from('<IIIIIIIIII', data, e_shoff + i * e_shentsize)
    secs.append(sh)
shstr = secs[e_shstrndx]
def secname(off):
    s = data[shstr[4] + off:]
    return s[:s.index(b'\0')].decode()
want = {'.rodata', '.data', '.data.rel.ro.local', '.data.rel.ro'}
out = []
for sh in secs:
    name = secname(sh[0])
    if name not in want: continue
    addr, off, size = sh[3], sh[4], sh[5]
    blob = data[off:off + size]
    i = 0
    n = len(blob)
    while i < n:
        j = blob.find(b'\0', i)
        if j < 0: j = n
        chunk = blob[i:j]
        if chunk:
            try:
                s = chunk.decode('utf-8')
                if all((c.isprintable() or c in '\t\n\r') for c in s):
                    # also record suffixes? no: record only full strings starting at i
                    out.append((addr + i, name, s))
            except UnicodeDecodeError:
                pass
        i = j + 1
with open(os.path.join(BASE, 'cstrings.tsv'), 'w') as f:
    for a, n, s in out:
        f.write(f'{a:08x}\t{n}\t' + s.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r') + '\n')
print(len(out), 'strings')
