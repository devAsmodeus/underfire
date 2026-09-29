import os, json, collections
ROOT='raw'
LAYERS=['apk','obb_main','obb_patch']
idx={}
for L in LAYERS:
    base=os.path.join(ROOT,L,'assets')
    for dp,dn,fn in os.walk(base):
        for f in fn:
            if f=='.DS_Store': continue
            full=os.path.join(dp,f)
            rel=os.path.relpath(full,base)
            idx[rel]={'layer':L,'path':full,'size':os.path.getsize(full)}
OUT='docs/research/requirements/index.json'
json.dump(idx,open(OUT,'w'))
print('files',len(idx))
ext=collections.Counter(); extsz=collections.Counter()
top=collections.Counter(); topsz=collections.Counter()
for rel,v in idx.items():
    e=rel.split('.',1)[1] if '.' in os.path.basename(rel) else ''
    e=os.path.basename(rel).split('.',1)[1] if '.' in os.path.basename(rel) else ''
    ext[e]+=1; extsz[e]+=v['size']
    t=rel.split('/')[0]
    top[t]+=1; topsz[t]+=v['size']
for e,c in ext.most_common(40): print(f'{e:20s} {c:6d} {extsz[e]/1e6:9.1f} MB')
print()
for t,c in top.most_common(): print(f'{t:20s} {c:6d} {topsz[t]/1e6:9.1f} MB')
