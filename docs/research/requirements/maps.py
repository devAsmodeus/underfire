import json, collections, statistics as st
from lxml import etree
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
maps=[k for k in idx if k.startswith('config/maps/')]
paths=collections.Counter(); attrs=collections.defaultdict(collections.Counter)
dims=[]; vis=[]; per=collections.defaultdict(list); srcs=collections.Counter()
parser=etree.XMLParser(recover=True, huge_tree=True)
bad=0
for k in maps:
    try:
        t=etree.parse(idx[k]['path'],parser)
    except Exception as e:
        bad+=1; continue
    r=t.getroot()
    if r is None: bad+=1; continue
    cnt=collections.Counter()
    for el in r.iter():
        if not isinstance(el.tag,str): continue
        tag=etree.QName(el).localname
        # path of tags
        anc=[etree.QName(a).localname for a in el.iterancestors() if isinstance(a.tag,str)][::-1]
        p='/'.join(anc[1:]+[tag]) if anc else tag
        paths[p]+=1; cnt[p]+=1
        for a in el.attrib: attrs[p][a]+=1
    for m in r.iter('map'):
        dims.append((int(m.get('width',0)),int(m.get('length',0)),k))
        v=m.find('visual')
        if v is not None:
            vis.append((int(float(v.get('width',0))),int(float(v.get('height',0))),v.get('src')))
            srcs[v.get('src')]+=1
    for p,c in cnt.items(): per[p].append(c)
print('maps',len(maps),'bad',bad)
for p,c in paths.most_common():
    arr=per[p]
    print(f'{p:45s} total={c:6d} files={len(arr):4d} max/file={max(arr):5d} med={st.median(arr):6.0f}  attrs={dict(attrs[p])}')
w=[d[0] for d in dims]; l=[d[1] for d in dims]
print('grid width',min(w),st.median(w),max(w),' length',min(l),st.median(l),max(l))
print('biggest grids',sorted(dims,key=lambda d:d[0]*d[1])[-5:])
vw=[v[0] for v in vis]; vh=[v[1] for v in vis]
print('visual w',min(vw),st.median(vw),max(vw),' h',min(vh),st.median(vh),max(vh))
print('biggest visuals',sorted(vis,key=lambda v:v[0]*v[1])[-5:])
print('unique visual srcs',len(srcs))
