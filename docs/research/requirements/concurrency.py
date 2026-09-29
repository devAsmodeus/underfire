import json, collections, statistics as st, bisect
from lxml import etree
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
C=json.load(open('data/config.json'))
TPS=30  # global_params/ticks_per_second
parser=etree.XMLParser(recover=True)
def spawn_times(s):
    t=0; out=[]
    for el in s.find('script') if s.find('script') is not None else []:
        if not isinstance(el.tag,str): continue
        if el.tag=='sleep':
            try: t+=float(el.text)
            except: pass
        elif el.tag=='spawn': out.append(t/TPS)
    return out
res={10:[],20:[],30:[],'all':[]}; per_mission={10:[],20:[],'all':[]}
for m in C['missions']:
    k='config/missions/'+m['attr']['path']
    if k not in idx: continue
    mm=etree.parse(idx[k]['path'],parser).getroot().find('.//mission')
    sp={s.get('tag'):s for s in mm.findall('./script_spawners/script_spawner')}
    best={10:0,20:0,'all':0}
    for w in mm.findall('./waypoints/waypoint'):
        d=w.find('defend')
        if d is None: continue
        times=[]
        for x in d.findall('./script_spawner'):
            s=sp.get(x.get('tag'))
            if s is not None: times+=spawn_times(s)
        times.sort()
        if not times: continue
        for L in (10,20,30):
            mx=0
            for i,t in enumerate(times):
                j=bisect.bisect_right(times,t+L)  # spawned within [t,t+L]
                mx=max(mx,j-i)
            res[L].append(mx)
            if L in best: best[L]=max(best[L],mx)
        res['all'].append(len(times)); best['all']=max(best['all'],len(times))
    for L in best: per_mission[L].append(best[L])
def q(v): v=sorted(v); return f"median {st.median(v):.0f}, p90 {v[int(.9*len(v))]:.0f}, max {v[-1]:.0f}"
print('phases',len(res['all']))
for L in (10,20,30): print(f'enemies spawned within any {L}s window of a defend phase: {q(res[L])}')
print('enemies per defend phase total:',q(res['all']))
print('per mission worst phase, 20s window:',q(per_mission[20]))
