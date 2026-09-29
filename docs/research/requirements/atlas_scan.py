import json, collections, os
S='docs/research/requirements/'
idx=json.load(open(S+'index.json')); pkm=json.load(open(S+'pkm.json'))
atl=[k for k in idx if k.endswith('.atlas')]
nf=collections.Counter(); frames=0; uniq_rects=0; bad=[]; hdr=collections.Counter()
used_area=collections.Counter(); tex_area=collections.Counter(); missing_tex=0
cat_frames=collections.Counter()
res={}
for k in atl:
    lines=open(idx[k]['path'],encoding='utf-8',errors='replace').read().splitlines()
    if not lines: bad.append(k); continue
    hdr[lines[0].split(':')[0]]+=1
    rects=set(); n=0; maxx=maxy=0
    for ln in lines[1:]:
        if not ln.strip(): continue
        p=ln.rstrip('\t').split('\t')
        nf[len(p)]+=1
        if len(p)<5: bad.append((k,ln)); continue
        x,y,w,h=map(int,p[1:5]); n+=1
        rects.add((x,y,w,h))
        maxx=max(maxx,x+w); maxy=max(maxy,y+h)
    frames+=n; uniq_rects+=len(rects)
    ua=sum(w*h for _,_,w,h in rects)
    t=k[:-6]+'.pkm.ccz'
    cat=k.split('/')[1]
    cat_frames[cat]+=n
    if t in pkm:
        used_area[cat]+=ua; tex_area[cat]+=pkm[t]['ow']*pkm[t]['oh']
    else: missing_tex+=1
    res[k]={'frames':n,'uniq':len(rects),'bbox':(maxx,maxy),'used':ua}
json.dump(res,open(S+'atlas.json','w'))
print('atlases',len(atl),'frames',frames,'unique rects',uniq_rects,'fields/line',nf,'headers',hdr,'bad',len(bad),bad[:3],'missing tex',missing_tex)
for c in tex_area: print(f'  {c:12s} frames={cat_frames[c]:7d} fill={used_area[c]/tex_area[c]*100:5.1f}%  used RGBA={used_area[c]*4/2**20:7.1f} MiB  tex RGBA={tex_area[c]*4/2**20:7.1f} MiB')
# textures without atlas
noatl=[k for k in pkm if k[:-8]+'.atlas' not in idx]
c=collections.Counter(k.split('/')[1] for k in noatl)
print('pkm without atlas:',len(noatl),c)
