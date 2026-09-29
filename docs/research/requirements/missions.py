import json, collections, statistics as st
from lxml import etree
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
C=json.load(open('data/config.json'))
used=set((m.get('attr') or {}).get('path') for m in C['missions'])
ms=[k for k in idx if k.startswith('config/missions/')]
parser=etree.XMLParser(recover=True)
paths=collections.Counter(); attrs=collections.defaultdict(collections.Counter); per=collections.defaultdict(list)
mis=[]
for k in ms:
    r=etree.parse(idx[k]['path'],parser).getroot()
    if r is None: continue
    cnt=collections.Counter()
    for el in r.iter():
        if not isinstance(el.tag,str): continue
        tag=etree.QName(el).localname
        anc=[etree.QName(a).localname for a in el.iterancestors() if isinstance(a.tag,str)][::-1]
        p='/'.join(anc[1:]+[tag]); 
        # collapse item-level tags in on_victory etc
        paths[p]+=1; cnt[p]+=1
        for a in el.attrib: attrs[p][a]+=1
    for p,c in cnt.items(): per[p].append(c)
    for m in r.iter('mission'):
        spawns=m.findall('.//spawn')
        sleeps=[float(s.text) for s in m.findall('.//sleep') if s.text and s.text.strip().replace('.','',1).isdigit()]
        mis.append({'file':k,'type':m.get('type'),'map':m.get('map'),'spawn':len(spawns),'script_spawners':len(m.findall('.//script_spawner')),
                    'sleep_total':sum(sleeps),'units':collections.Counter(s.get('type') for s in spawns),
                    'used': k.replace('config/missions/','') in used})
json.dump(mis,open(S+'missions.json','w'),default=list)
print('mission files',len(ms),'missions',len(mis),'referenced by config',sum(m['used'] for m in mis))
for p,c in paths.most_common(70):
    arr=per[p]
    print(f'{p:70s} {c:6d} files={len(arr):4d} max={max(arr):4d}  {dict(attrs[p].most_common(8))}')
