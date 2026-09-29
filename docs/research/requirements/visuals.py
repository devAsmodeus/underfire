import json, collections, statistics as st
from lxml import etree
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
vis=[k for k in idx if k.startswith('config/visuals/')]
parser=etree.XMLParser(recover=True)
out={}
agg=collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
elemtags=collections.Counter(); attrset=collections.defaultdict(set)
for k in vis:
    cat=k.split('/')[2] if k.count('/')>2 else '(root)'
    r=etree.parse(idx[k]['path'],parser).getroot()
    if r is None: continue
    for el in r.iter():
        if isinstance(el.tag,str):
            elemtags[etree.QName(el).localname]+=1
            for a in el.attrib: attrset[etree.QName(el).localname].add(a)
    dirs=r.findall('.//direction')
    info={'cat':cat,'name':r.get('name'),'fps':r.get('fps'),'scale':r.get('scale'),'atlases':r.get('atlases'),
          'dirs':[d.get('name') for d in dirs],'states':{},'layers_max':0,'frames_total':0,'hit':sum(1 for d in dirs if d.get('hitArea'))}
    uniq=set()
    for d in dirs:
        for s in d.findall('.//state'):
            ls=s.findall('.//layer')
            info['layers_max']=max(info['layers_max'],len(ls))
            fc=[int(l.get('frameCount') or 0) for l in ls]
            info['states'].setdefault(s.get('name'),max(fc) if fc else 0)
            for l in ls:
                for f in (l.get('frames') or '').split(','):
                    if f.strip(): uniq.add((d.get('name'),f.strip(),l.get('atlas') or ''))
    info['frames_unique']=len(uniq)
    out[k]=info
    a=agg[cat]
    a['ndirs'][len(dirs)]+=1
    a['dirset'][','.join(sorted(set(info['dirs'])))]+=1
    a['fps'][info['fps']]+=1
    a['scale'][info['scale']]+=1
    a['nstates'][len(info['states'])]+=1
    a['layers_max'][info['layers_max']]+=1
    for s,fc in info['states'].items():
        a['state'][s]+=1
        a['fc'][fc]+=1
json.dump(out,open(S+'visuals.json','w'),ensure_ascii=False)
print('visual files',len(out))
print('element tags',elemtags)
for t,s in attrset.items(): print(' ',t,sorted(s))
for cat,a in sorted(agg.items(),key=lambda x:-sum(x[1]['ndirs'].values())):
    n=sum(a['ndirs'].values())
    print(f'\n== {cat}: {n} visuals')
    print('  #dirs:',dict(sorted(a['ndirs'].items())))
    print('  dirsets:',a['dirset'].most_common(6))
    print('  fps:',dict(a['fps']),' scale:',dict(a['scale'].most_common(6)))
    print('  #states:',dict(sorted(a['nstates'].items())),' max layers/state:',dict(sorted(a['layers_max'].items())))
    print('  states:',a['state'].most_common(25))
    fcs=[]
    for fc,c in a['fc'].items(): fcs+= [fc]*c
    print('  frames/state: min',min(fcs),'median',st.median(fcs),'p90',sorted(fcs)[int(len(fcs)*0.9)],'max',max(fcs))
    fu=[i['frames_unique'] for i in out.values() if i['cat']==cat]
    print('  unique frames/visual: median',st.median(fu),'max',max(fu),'sum',sum(fu))
