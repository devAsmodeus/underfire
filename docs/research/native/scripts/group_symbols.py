#!/usr/bin/env python3
"""Group demangled dynamic symbols of libinferno.so by namespace / class.
Input: syms_defined.tsv (addr, size, type, mangled, demangled)
Output: several text files in the same dir."""
import sys, os, re, collections, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = []
with open(os.path.join(BASE, 'syms_defined.tsv')) as f:
    for line in f:
        p = line.rstrip('\n').split('\t')
        if len(p) < 5: continue
        rows.append(p)

PREFIXES = ['vtable for ', 'typeinfo for ', 'typeinfo name for ', 'VTT for ',
            'construction vtable for ', 'non-virtual thunk to ', 'virtual thunk to ',
            'guard variable for ', 'covariant return thunk to ', 'reference temporary for ']

def split_top(s, sep='::'):
    parts, depth, cur, i = [], 0, '', 0
    while i < len(s):
        c = s[i]
        if c in '<(': depth += 1
        elif c in '>)': depth -= 1
        if depth == 0 and s.startswith(sep, i):
            parts.append(cur); cur = ''; i += len(sep); continue
        cur += c; i += 1
    parts.append(cur)
    return parts

def qualname(d):
    kind = 'func'
    for p in PREFIXES:
        if d.startswith(p):
            kind = p.strip(); d = d[len(p):]
            if p.startswith('construction vtable for '):
                d = d.split('-in-')[0]
            break
    # strip parameter list: find first '(' at angle depth 0 that is not part of operator()
    depth = 0; cut = None; i = 0
    while i < len(d):
        c = d[i]
        if d.startswith('operator()', i): i += len('operator()'); continue
        if d.startswith('operator<<', i) or d.startswith('operator>>', i): i += 10; continue
        if d.startswith('operator<=', i) or d.startswith('operator>=', i) or d.startswith('operator->', i): i += 10; continue
        if d.startswith('operator<', i) or d.startswith('operator>', i): i += 9; continue
        if c == '<': depth += 1
        elif c == '>': depth -= 1
        elif c == '(' and depth == 0:
            cut = i; break
        i += 1
    q = d[:cut] if cut is not None else d
    # remove return type for templated functions: last depth-0 space not inside "operator X"
    depth = 0; last_space = -1
    for i, c in enumerate(q):
        if c == '<': depth += 1
        elif c == '>': depth -= 1
        elif c == ' ' and depth == 0 and not q[:i].endswith('operator') and not q[max(0,i-8):i].endswith('operator'):
            last_space = i
    if last_space >= 0 and 'operator' not in q[last_space-8:last_space+1]:
        q = q[last_space+1:]
    return kind, q

def classify(q, kind):
    parts = split_top(q)
    if kind in ('vtable for', 'typeinfo for', 'typeinfo name for', 'VTT for', 'construction vtable for'):
        scope = parts; member = '<' + kind + '>'
    else:
        scope = parts[:-1]; member = parts[-1]
    return parts, scope, member

C_LIBS = [
    ('openssl', re.compile(r'^(ASN1|ACCESS_DESCRIPTION|AES|BIO|BN|BUF|CRYPTO|DES|DH|DSA|EC|ENGINE|ERR|EVP|HMAC|MD5|MD4|OBJ|OPENSSL|PEM|PKCS|RAND|RC2|RC4|RSA|SHA|SSL|TLS|X509|X509V3|d2i|i2d|i2a|a2i|i2v|v2i|i2s|s2i|i2t|asn1|bn_|BN_|CMS|OCSP|COMP|CONF|DSO|ECDH|ECDSA|UI|TS|lh_|sk_|OBJ_|NCONF|NETSCAPE|POLICY|GENERAL|DIST|AUTHORITY|BASIC|EXTENDED|NOTICEREF|USERNOTICE|SXNET|PROXY|CRL|DIRECTORY|IPAddress|ASIdent|ASRange|ASIdOr|IPAddr|PBE|PBKDF|PBEPARAM|PBE2PARAM|PKEY|OTHERNAME|EDIPARTY|ISSUING|POLICYINFO|POLICYQUALINFO|NAME_CONSTRAINTS|GENERAL_SUBTREE|ssl|tls|dtls|DTLS|SEED|CAMELLIA|Camellia|BF_|CAST|IDEA|MDC2|RIPEMD|WHIRLPOOL|CMAC|KRB5|SRP|ERR_|_CONF|private_|fips|FIPS|ec_|dh_|dsa_|rsa_|x509|pem_|evp_|EVP_|o2i|i2o|PEM_|CRYPTO_|OPENSSL_|X509_)'), ),
    ('libcurl', re.compile(r'^(curl_|Curl_|curlx_)')),
    ('libpng', re.compile(r'^png_')),
    ('libjpeg', re.compile(r'^(jpeg_|jinit_|jcopy_|jdiv_|jround_|jzero_|jpeg)')),
    ('libtiff', re.compile(r'^(TIFF|_TIFF|tiff)')),
    ('libwebp', re.compile(r'^(WebP|VP8|VP8L)')),
    ('zlib/unzip', re.compile(r'^(unz|zip|inflate|deflate|crc32|adler32|gz)')),
    ('sqlite3', re.compile(r'^sqlite3')),
    ('libxml2', re.compile(r'^(xml|html|xpath|xsl)')),
    ('lua', re.compile(r'^(lua|luaL|luaopen|tolua)')),
    ('chipmunk', re.compile(r'^(cp[A-Z]|_cp)')),
    ('jni', re.compile(r'^(Java_|JNI_)')),
    ('freetype', re.compile(r'^(FT_|ft_|FTC_|af_|ps_|t1_|cff_|tt_)')),
    ('kazmath', re.compile(r'^(km|lowestRoot|kmGL)')),
]

ns_counter = collections.Counter()
class_members = collections.defaultdict(set)     # class -> set(member)
class_kinds = collections.defaultdict(set)
class_ns = {}
c_counter = collections.Counter()
c_examples = collections.defaultdict(list)
out_rows = []
for addr, size, typ, mangled, dem in rows:
    if not mangled.startswith('_Z'):
        lib = 'other-C'
        for name, rx in C_LIBS:
            if rx.match(mangled):
                lib = name; break
        c_counter[lib] += 1
        if len(c_examples[lib]) < 40: c_examples[lib].append(mangled)
        out_rows.append((addr, size, typ, 'C:' + lib, '', mangled, dem))
        continue
    kind, q = qualname(dem)
    parts, scope, member = classify(q, kind)
    top = parts[0] if len(parts) > 1 or kind != 'func' else '(global-func)'
    # strip template args from top ns for grouping
    top_clean = re.sub(r'<.*', '', top)
    if kind == 'func' and len(parts) == 1:
        top_clean = '(global-func)'
    ns_counter[top_clean] += 1
    cls = '::'.join(scope) if scope else '(free)'
    class_members[cls].add(member)
    class_kinds[cls].add(kind)
    out_rows.append((addr, size, typ, top_clean, cls, member, dem))

with open(os.path.join(BASE, 'symbols_all_grouped.tsv'), 'w') as f:
    f.write('addr\tsize\ttype\tgroup\tscope\tmember\tdemangled\n')
    for r in sorted(out_rows, key=lambda r: (r[3], r[4], r[5])):
        f.write('\t'.join(r) + '\n')

with open(os.path.join(BASE, 'symbols_namespace_counts.txt'), 'w') as f:
    f.write('# C++ symbols by top-level scope (first component of qualified name)\n')
    for k, v in ns_counter.most_common():
        f.write(f'{v:7d}  {k}\n')
    f.write('\n# non-C++ (C) symbols by library (heuristic prefix match)\n')
    for k, v in c_counter.most_common():
        f.write(f'{v:7d}  {k}   e.g. {", ".join(c_examples[k][:8])}\n')

# class files per group
def top_of(cls):
    return re.sub(r'<.*', '', split_top(cls)[0])

groups = collections.defaultdict(list)
for cls in class_members:
    groups[top_of(cls)].append(cls)

def dump_group(fname, pred, title):
    with open(os.path.join(BASE, fname), 'w') as f:
        f.write(f'# {title}\n# format: class [kinds] (N members): members...\n')
        sel = sorted(c for c in class_members if pred(c))
        for cls in sel:
            mem = sorted(m for m in class_members[cls] if not m.startswith('<'))
            kinds = ','.join(sorted(k for k in class_kinds[cls] if k != 'func'))
            f.write(f'\n{cls} [{kinds}] ({len(mem)}):\n')
            for m in mem:
                f.write(f'    {m}\n')
    return len(sel)

KNOWN_LIBS = {'std', '__gnu_cxx', 'CryptoPP', 'cocos2d', 'CocosDenshion', 'tinyxml2', 'pugi', 'rapidxml',
              '__cxxabiv1', '(global-func)', 'boost', 'CSJson', 'avalon', 'skzk', 'Json', 'log4cplus', 'FMOD', 'jni', 'google'}
n1 = dump_group('classes_cocos2d.txt', lambda c: top_of(c) in ('cocos2d', 'CocosDenshion'), 'cocos2d / CocosDenshion classes')
n2 = dump_group('classes_inferno_ns.txt', lambda c: top_of(c) == 'inferno', 'namespace inferno:: (logic core / "server" side)')
n3 = dump_group('classes_game_global.txt', lambda c: top_of(c) not in KNOWN_LIBS and not c.startswith('b2') and top_of(c) not in ('inferno',), 'global-namespace game/engine classes (not cocos2d/inferno/std/CryptoPP)')
n4 = dump_group('classes_thirdparty.txt', lambda c: top_of(c) in ('tinyxml2', 'pugi', 'rapidxml', 'CSJson', 'avalon', 'skzk', 'Json', 'boost', 'log4cplus', 'google') or c.startswith('b2'), 'third-party C++ libs (xml/json/avalon/box2d/etc.)')
print('groups written', n1, n2, n3, n4)
print('top scopes:', ns_counter.most_common(60))
print('C libs:', c_counter.most_common())
