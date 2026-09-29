import json, collections, statistics as st
from lxml import etree
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
C=json.load(open('data/config.json'))
used=set((m.get('attr') or {}).get('path') for m in C['missions'])
parser=etree.XMLParser(recover=True)
rows=[]; sleeps=[]; unit_types=collections.Counter(); masks=collections.Counter()
for k in sorted(x for x in idx if x.startswith('config/missions/')):
    rel=k.replace('config/missions/','')
    if rel not in used: continue
    r=etree.parse(idx[k]['path'],parser).getroot()
    m=r.find('.//mission')
    sp={}
    for s in m.findall('./script_spawners/script_spawner'):
        spawns=s.findall('.//spawn'); sl=[]
        for x in s.findall('.//sleep'):
            try: sl.append(float(x.text))
            except: pass
        sleeps+=sl
        for x in spawns: unit_types[x.get('type')]+=1
        sp[s.get('tag')]={'n':len(spawns),'dur':sum(sl),'trigger':s.get('trigger')}
    total=sum(v['n'] for v in sp.values())
    wps=m.findall('./waypoints/waypoint')
    # enemies per waypoint phase: spawners referenced in defend (not in after)
    phase=[]; pts=[]
    for w in wps:
        d=w.find('defend')
        if d is None: continue
        tags=[x.get('tag') for x in d.findall('./script_spawner')]
        after=[x.get('tag') for x in d.findall('./after/spawn/script_spawner')]
        n=sum(sp.get(t,{'n':0})['n'] for t in tags)
        dur=max([sp.get(t,{'dur':0})['dur'] for t in tags] or [0])
        phase.append((n,dur,sum(sp.get(t,{'n':0})['n'] for t in after)))
        p=d.findall('./point'); pts.append(len(p))
        for x in p: masks[x.get('mask')]+=1
    # untriggered spawners (trigger absent => start immediately?)
    rows.append({'m':rel,'total':total,'nspawners':len(sp),'wps':len(wps),'phase':phase,'pts':pts,
                 'slot_points':len(m.findall('./slot_spawners/slot_spawner/points/point'))})
json.dump(rows,open(S+'missions_stats.json','w'))
tot=[r['total'] for r in rows]; print('used missions',len(rows))
print('enemy spawns per mission: min',min(tot),'median',st.median(tot),'p90',sorted(tot)[int(.9*len(tot))],'max',max(tot))
ph=[p[0] for r in rows for p in r['phase']]
print('enemy spawns per waypoint phase (defend spawners): median',st.median(ph),'p90',sorted(ph)[int(.9*len(ph))],'max',max(ph))
phd=[p[1] for r in rows for p in r['phase']]
print('longest spawner script per phase (sum of sleeps): median',st.median(phd),'p90',sorted(phd)[int(.9*len(phd))],'max',max(phd))
print('rate: spawns per 100 sleep-units per phase: median',st.median([p[0]/p[1]*100 for r in rows for p in r['phase'] if p[1]>0]))
pp=[x for r in rows for x in r['pts']]
print('player defend points per waypoint: median',st.median(pp),'max',max(pp))
sp=[r['slot_points'] for r in rows]; print('initial slot points: median',st.median(sp),'max',max(sp))
print('waypoints per mission',collections.Counter(r['wps'] for r in rows))
print('spawners per mission: median',st.median([r['nspawners'] for r in rows]),'max',max(r['nspawners'] for r in rows))
print('sleep values: ',collections.Counter(sleeps).most_common(12),'median',st.median(sleeps))
print('defend point masks',masks.most_common())
print('distinct enemy types spawned',len(unit_types), unit_types.most_common(10))
print('biggest missions',sorted(rows,key=lambda r:-r['total'])[:3])
