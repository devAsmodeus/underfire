#!/usr/bin/env python3
"""Lightweight Thumb (ARMv5TE, 16-bit + BL pair) scanner over exported functions of libinferno.so.
NOT a full disassembler: it only recognises
  * LDR Rt,[PC,#imm8*4]  followed by  ADD Rt,PC     -> PC-relative address (strings/data)
  * BL/BLX pairs (11110 + 11111/11101)                  -> direct call targets
and maps results to dynamic symbols / .rodata strings.
Outputs: xref_strings.tsv (function -> string), callgraph.tsv (caller -> callee)."""
import struct, bisect, os, sys, collections
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = open(os.path.join(BASE, 'bin/libinferno.so'), 'rb').read()
symoff, symsz, stroff = 0x148, 0xef140, 0xef288
dem = {}
for line in open(os.path.join(BASE, 'syms_defined.tsv')):
    a, sz, t, m, d = line.rstrip('\n').split('\t')
    dem[m] = d
funcs = []
for i in range(symsz // 16):
    name, value, size, info, other, shndx = struct.unpack_from('<IIIBBH', data, symoff + 16*i)
    if info & 0xf == 2 and shndx != 0:
        n = data[stroff+name:data.index(b'\0', stroff+name)].decode()
        funcs.append((value & ~1, size, bool(value & 1), dem.get(n, n)))
# dedupe by start (aliases like C1/C2 ctors)
bystart = {}
for s, sz, th, n in funcs:
    if s not in bystart or len(n) < len(bystart[s][2]):
        bystart[s] = (sz, th, n)
# PLT stubs: PLT0 is 20 bytes at .plt start, then 12-byte entries in .rel.plt order
relplt, relsz, plt0 = 0x672160, 0x1030, 0x673190
for i in range(relsz // 8):
    off, info = struct.unpack_from('<II', data, relplt + 8*i)
    si = info >> 8
    nm, v, szz, inf, oth, shn = struct.unpack_from('<IIIBBH', data, symoff + 16*si)
    n = data[stroff+nm:data.index(b'\0', stroff+nm)].decode()
    bystart[plt0 + 20 + 12*i] = (12, False, dem.get(n, n) + '@plt')
starts = sorted(bystart)
# strings map (.rodata) : addr -> string ; also sorted list to find containing string
strs = {}
for line in open(os.path.join(BASE, 'cstrings.tsv')):
    a, sec, s = line.rstrip('\n').split('\t', 2)
    strs[int(a, 16)] = s
saddrs = sorted(strs)
RO_LO, RO_HI = 0xcfcc88, 0xcfcc88 + 0xff420
def string_at(addr):
    if addr in strs: return strs[addr], 0
    i = bisect.bisect_right(saddrs, addr) - 1
    if i >= 0:
        a = saddrs[i]; s = strs[a]
        if a <= addr < a + len(s.encode('utf-8')): return s, addr - a
    return None, None
def func_at(addr):
    i = bisect.bisect_right(starts, addr) - 1
    if i >= 0:
        s = starts[i]; sz, th, n = bystart[s]
        if s <= addr < s + max(sz, 1): return s, n
    return None, None
def hw(addr): return struct.unpack_from('<H', data, addr)[0]
def word(addr): return struct.unpack_from('<I', data, addr)[0]
xs = open(os.path.join(BASE, 'xref_strings.tsv'), 'w')
cg = open(os.path.join(BASE, 'callgraph.tsv'), 'w')
nstr = ncall = 0
for s in starts:
    sz, th, name = bystart[s]
    if not th or sz < 4: continue
    end = s + sz
    # pass 1: literal pool words
    lit = set(); pc = s
    while pc < end - 1:
        h = hw(pc)
        if (h >> 11) == 0b01001:
            la = ((pc + 4) & ~3) + (h & 0xff) * 4
            lit.add(la); lit.add(la + 2)
        if (h >> 11) in (0b11101, 0b11110, 0b11111): pc += 4
        else: pc += 2
    # pass 2
    pend = {}; pc = s
    while pc < end - 1:
        if pc in lit: pc += 2; continue
        h = hw(pc)
        top5 = h >> 11
        if top5 == 0b01001:  # LDR literal
            rt = (h >> 8) & 7
            la = ((pc + 4) & ~3) + (h & 0xff) * 4
            if la + 4 <= len(data): pend[rt] = word(la)
            pc += 2; continue
        if (h & 0xff78) == 0x4478:  # ADD Rd, PC (Rd = D:ddd)
            rd = (h & 7) | ((h >> 4) & 8)
            if rd in pend:
                target = (pend.pop(rd) + pc + 4) & 0xffffffff
                if RO_LO <= target < RO_HI:
                    st, off = string_at(target)
                    if st is not None:
                        xs.write(f'{s:08x}\t{name}\t{target:08x}\t{off}\t{st}\n'); nstr += 1
            pc += 2; continue
        if top5 == 0b11110 and pc + 2 < end:
            h2 = hw(pc + 2)
            if (h2 >> 11) in (0b11111, 0b11101):
                off = ((h & 0x7ff) << 12) | ((h2 & 0x7ff) << 1)
                if off & (1 << 22): off -= (1 << 23)
                tgt = pc + 4 + off
                if (h2 >> 11) == 0b11101: tgt &= ~3
                fs, fn = func_at(tgt)
                if not (fs is not None and fs == tgt) and tgt + 16 <= len(data):
                    # gold Thumb->ARM long-branch stub: bx pc; nop; ldr r12,[pc]; add pc,r12,pc; .word off
                    if hw(tgt) == 0x4778 and hw(tgt + 2) == 0x46c0 and word(tgt + 4) == 0xe59fc000 and word(tgt + 8) == 0xe08cf00f:
                        final = (tgt + 8 + 8 + word(tgt + 12)) & 0xffffffff
                        tgt = final
                        fs, fn = func_at(tgt)
                    elif hw(tgt) == 0x4778 and hw(tgt + 2) == 0x46c0 and word(tgt + 4) == 0xe59fc004 and word(tgt + 8) == 0xe08fc00c and word(tgt + 12) == 0xe12fff1c:
                        # Thumb->Thumb long branch via ARM: ldr r12,[pc,#4]; add r12,pc,r12; bx r12; .word off
                        final = (tgt + 8 + 8 + word(tgt + 16)) & 0xfffffffe
                        tgt = final
                        fs, fn = func_at(tgt)
                    elif word(tgt) == 0xe59fc000 and word(tgt + 4) == 0xe08cf00f:  # ARM-state stub reached via BLX
                        final = (tgt + 4 + 8 + word(tgt + 8)) & 0xffffffff
                        tgt = final
                        fs, fn = func_at(tgt)
                if fs is not None and fs == tgt:
                    cg.write(f'{s:08x}\t{name}\t{tgt:08x}\t{fn}\n'); ncall += 1
                for r in (0, 1, 2, 3): pend.pop(r, None)
                pc += 4; continue
        if top5 in (0b11101, 0b11110, 0b11111): pc += 4; continue
        # any other instruction writing low regs: we keep it simple (no invalidation)
        pc += 2
xs.close(); cg.close()
print('string xrefs', nstr, 'call edges', ncall)
