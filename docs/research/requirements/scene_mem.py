import json, collections, statistics as st, re, os
from lxml import etree
S='docs/research/requirements/'
idx=json.load(open(S+'index.json')); pkm=json.load(open(S+'pkm.json')); atl=json.load(open(S+'atlas.json'))
V=json.load(open(S+'visuals.json'))
C=json.load(open('data/config.json'))
MiB=2**20
# texture dir index
texdir=collections.defaultdict(list)
for k in pkm:
    texdir[os.path.dirname(k)].append(k)
def pot(k): r=pkm[k]; return r['ow']*r['oh']*4
def used(k):
    a=atl.get(k[:-8]+'.atlas')
    if a:
        w,h=a['bbox']; return ((w+3)//4*4)*((h+3)//4*4)*4
    return pot(k)
def vis_textures(src, direction=None):
    """src like 'units/praetorians_agressor' or 'buildings/military_factory_1'"""
    vx=V.get('config/visuals/'+src+'.xml')
    if vx and vx.get('name'): src=src.split('/')[0]+'/'+vx['name']
    base='textures_etc/'+src
    out=set()
    for d,ks in texdir.items():
        if d==base or d.startswith(base+'/'):
            if direction and src.startswith('buildings/'):
                rel=d[len(base):].strip('/')
                if rel and rel!=direction: continue
                if not rel:
                    ks=[k for k in ks if os.path.basename(k).split('_')[0].split('.')[0]==direction]
                    # skip depth3 twins if depth4 exists
                    if (base+'/'+direction) in texdir: ks=[]
            out.update(ks)
    return out
def mem(ts): return sum(pot(k) for k in ts), sum(used(k) for k in ts)
# check resolution coverage for soldiers
sol={s['attr']['type']:s for s in C['soldiers']}
def sol_visual(t):
    s=sol.get(t)
    if not s: return None
    for c in s.get('children',[]):
        if c['tag']=='visual': return (c.get('attr') or {}).get('src')
miss=[t for t in sol if sol_visual(t) and not vis_textures(sol_visual(t))]
print('soldiers',len(sol),'with no textures found',len(miss),miss[:8])
# per-visual memory for unit-like
uv=[]
for k,v in V.items():
    if v['cat'] in ('units','mobs'):
        src=k.replace('config/visuals/','')[:-4]
        p,u=mem(vis_textures(src)); uv.append((p,u,src))
print('unit/mob visuals',len(uv),'POT MiB/visual median',round(st.median(p for p,_,_ in uv)/MiB,1),'max',round(max(p for p,_,_ in uv)/MiB,1),
      ' used median',round(st.median(u for _,u,_ in uv)/MiB,1))
# building: per visual per direction
bv=[]
for k,v in V.items():
    if v['cat']=='buildings':
        src=k.replace('config/visuals/','')[:-4]
        for d in v['dirs'][:1]:
            p,u=mem(vis_textures(src,d)); bv.append((p,u,src,d))
print('building visual-dirs',len(bv),'POT MiB median',round(st.median(p for p,_,_,_ in bv)/MiB,2),'p90',round(sorted(p for p,_,_,_ in bv)[int(.9*len(bv))]/MiB,1),'max',round(max(p for p,_,_,_ in bv)/MiB,1))
# ---- effects/splatter resolution through behaviors
beh={b['attr']['type']:b for b in C['behaviors']}
eff={e['attr']['type']:e for e in C['effects']}
spl={s['attr']['type']:s for s in C['splatters']}
def walk(n,f):
    f(n)
    for c in n.get('children') or []: walk(c,f)
def fx_for_behavior(bname,seen):
    vis=set()
    if not bname or bname in seen: return vis
    seen.add(bname); b=beh.get(bname)
    if not b: return vis
    def f(n):
        a=n.get('attr') or {}
        if n['tag'] in ('cast','cast_visual') and a.get('effect'):
            e=eff.get(a['effect'])
            if e:
                if e['attr'].get('visual'): vis.add(e['attr']['visual'])
                vis.update(fx_for_behavior(e['attr'].get('behavior'),seen))
        if n['tag']=='add_splatter_to_target' and a.get('type') in spl:
            vis.add(spl[a['type']]['attr']['visual'])
        if n['tag']=='add_tracer_to_target': vis.add('effects/tracers')
    walk(b,f); return vis
def soldier_fx(t):
    s=sol.get(t); out=set()
    if not s: return out
    for key in ('attack_behavior','defend_behavior'):
        out|=fx_for_behavior(s['attr'].get(key),set())
    for c in s.get('children',[]):
        if c['tag']=='splatters':
            for x in c.get('children') or []:
                sp=spl.get((x.get('text') or '').strip())
                if sp: out.add(sp['attr']['visual'])
    return out
# ---- UI
def ui(defn):
    ks=[k for k in pkm if k.startswith(f'textures_etc/interface/{defn}/battle/')]
    for extra in ['frames','glow_long','glow_short','frames_additional','button_plus','button_close','icons']:
        ks+= [k for k in pkm if re.match(rf'textures_etc/interface/{defn}/city/{extra}(_\d+)?\.pkm\.ccz$',k)]
    return set(ks)
uiHD=mem(ui('1024x768')); uiSD=mem(ui('1024x768_sd'))
print('battle UI HD POT/used MiB',round(uiHD[0]/MiB),round(uiHD[1]/MiB),' SD',round(uiSD[0]/MiB),round(uiSD[1]/MiB))
# ---- missions
maps={m['attr']['type']:m['attr']['path'] for m in C['maps']}
parser=etree.XMLParser(recover=True, huge_tree=True)
# player army assumption
player=['praetorian_light','praetorian_medium','praetorian_heavy','scarlett_ney','titan_squad']
pl_t=set(); pl_fx=set()
for t in player:
    v=sol_visual(t)
    if v: pl_t|=vis_textures(v)
    pl_fx|=soldier_fx(t)
print('player army visuals',[sol_visual(t) for t in player],'POT MiB',round(mem(pl_t)[0]/MiB))
rows=[]
for m in C['missions']:
    path=m['attr']['path']; k='config/missions/'+path
    if k not in idx: continue
    r=etree.parse(idx[k]['path'],parser).getroot(); mm=r.find('.//mission')
    mp=mm.get('map'); mk='config/maps/'+maps.get(mp,'')
    if mk not in idx: continue
    mr=etree.parse(idx[mk]['path'],parser).getroot().find('.//map')
    vsrc=mr.find('visual').get('src')   # e.g. mission/side_1_1_map_01
    bg=set(k2 for k2 in texdir.get(os.path.dirname('textures_etc/maps/'+vsrc),[]) if os.path.basename(k2).startswith(os.path.basename(vsrc)+'_'))
    # content size from back_atlas
    bx='textures_etc/maps/'+vsrc+'.xml'; bg_used=0
    if bx in idx:
        for fr in etree.parse(idx[bx]['path'],parser).getroot().iter('frame'):
            bg_used+=int(fr.get('width'))*int(fr.get('height'))*4
    obs=set()
    for o in mr.iter('obstacle'):
        if o.get('visible')=='0': continue
        v=o.get('visual') or ''
        mt=re.match(r'(buildings/.+)_([nsew])$',v)
        if mt: obs|=vis_textures(mt.group(1),mt.group(2))
        elif v: obs|=vis_textures(v)
    en_types=set(s.get('type') for s in mm.iter('spawn'))
    en=set(); fx=set()
    for t in en_types:
        v=sol_visual(t)
        if v: en|=vis_textures(v)
        fx|=soldier_fx(t)
    fx|=pl_fx
    fxt=set()
    for v in fx: fxt|=vis_textures(v)
    for sv in mm.iter('visual'):
        if sv.get('src'): fxt|=vis_textures('effects/'+sv.get('src')) | vis_textures(sv.get('src'))
    parts={'bg':(sum(pot(x) for x in bg),bg_used or sum(pot(x) for x in bg)),'obstacles':mem(obs),'enemies':mem(en),'player':mem(pl_t),'fx':mem(fxt),'ui':uiHD}
    allt=bg|obs|en|pl_t|fxt|ui('1024x768')
    rows.append({'m':path,'types':len(en_types),'parts':parts,'total_pot':sum(p[0] for p in parts.values()),'total_used':sum(p[1] for p in parts.values()),'ntex':len(allt)})
json.dump(rows,open(S+'scene_mem.json','w'))
def q(vals):
    vals=sorted(vals); return f"median {st.median(vals)/MiB:.0f}  p90 {vals[int(.9*len(vals))]/MiB:.0f}  max {vals[-1]/MiB:.0f} MiB"
print('missions evaluated',len(rows))
print('enemy types per mission: median',st.median(r['types'] for r in rows),'max',max(r['types'] for r in rows))
for part in ['bg','obstacles','enemies','player','fx','ui']:
    print(f'  {part:10s} POT: {q([r["parts"][part][0] for r in rows])} | used: {q([r["parts"][part][1] for r in rows])}')
print('  TOTAL      POT:',q([r['total_pot'] for r in rows]),'| used:',q([r['total_used'] for r in rows]))
print('  textures per battle scene: median',st.median(r['ntex'] for r in rows),'max',max(r['ntex'] for r in rows))
print('heaviest',[(r['m'],round(r['total_pot']/MiB),r['types']) for r in sorted(rows,key=lambda r:-r['total_pot'])[:3]])
# city scene estimate
city_bg=[k for k in pkm if re.match(r'textures_etc/maps/city/city_1_\d_\d\.pkm\.ccz',k)]
cb=sum(pot(k) for k in city_bg)
print('city bg tiles',len(city_bg),'POT MiB',round(cb/MiB),' content MiB',round(3392*2452*4/MiB))
bp=sorted(p for p,_,_,_ in bv); bu=sorted(u for _,u,_,_ in bv)
for n in (20,40,60):
    print(f'  city with {n} distinct building visuals: ~{n*st.median(bp)/MiB:.0f} MiB (median) .. {n*st.mean(bp)/MiB:.0f} MiB (mean) POT; used ~{n*st.mean(bu)/MiB:.0f}')
def uic(defn):
    ks=[k for k in pkm if k.startswith(f'textures_etc/interface/{defn}/city/')]; return mem(set(ks))
print('city UI (all city atlases) HD',[round(x/MiB) for x in uic('1024x768')],'SD',[round(x/MiB) for x in uic('1024x768_sd')])
cz=set()
for k,v in V.items():
    if v['cat']=='citizens': cz|=vis_textures(k.replace('config/visuals/','')[:-4])
print('all citizens POT MiB',round(mem(cz)[0]/MiB))
