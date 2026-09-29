import json, collections
S='docs/research/requirements/'
res=json.load(open(S+'pkm.json'))
print('other:',[(k,r) for k,r in res.items() if r['ew']!=r['ow']])
sz=collections.Counter((r['ow'],r['oh']) for r in res.values())
print('size distribution (ow x oh):')
for s,c in sorted(sz.items(),key=lambda x:-x[0][0]*x[0][1]): print(f'  {s[0]}x{s[1]}: {c}')
def cat(k):
    p=k.split('/')
    return p[1] if len(p)>2 else '(root)'
tot=collections.Counter(); n=collections.Counter(); comp=collections.Counter(); etc=collections.Counter()
for k,r in res.items():
    c=cat(k)
    tot[c]+=r['ow']*r['oh']*4; n[c]+=1; comp[c]+=r['csize']; etc[c]+=r['ulen']
T=sum(tot.values())
print(f"TOTAL RGBA {T/2**20:.0f} MiB, files {sum(n.values())}, on-disk ccz {sum(comp.values())/2**20:.0f} MiB, ETC1 in-mem {sum(etc.values())/2**20:.0f} MiB")
for c in sorted(tot,key=lambda c:-tot[c]):
    print(f'  {c:12s} n={n[c]:5d} RGBA={tot[c]/2**20:8.1f} MiB  ccz={comp[c]/2**20:7.1f} MiB  etc1={etc[c]/2**20:7.1f} MiB')
# subcategories for buildings/units/mobs/effects/interface/background/maps
for top in ['maps','background','interface','effects','units','mobs','buildings','icons','citizens','turrets']:
    sub=collections.Counter(); sn=collections.Counter()
    for k,r in res.items():
        p=k.split('/')
        if len(p)>2 and p[1]==top:
            s=p[2] if len(p)>3 else '(files)'
            sub[s]+=r['ow']*r['oh']*4; sn[s]+=1
    print(top, 'subdirs:',len(sub), ' top:', [(s,sn[s],round(sub[s]/2**20,1)) for s,_ in sub.most_common(8)])
