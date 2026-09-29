import json, zlib, struct, collections
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
res={}
magic=collections.Counter(); ptype=collections.Counter()
for k,v in idx.items():
    if not k.endswith('.pkm.ccz'): continue
    with open(v['path'],'rb') as f:
        head=f.read(16); data=f.read(4096)
    magic[head[:4]]+=1
    comp_type,ver=struct.unpack('>HH',head[4:8]); ulen=struct.unpack('>I',head[12:16])[0]
    d=zlib.decompressobj()
    p=d.decompress(data,64)
    ptype[(p[:6],struct.unpack('>H',p[6:8])[0])]+=1
    ew,eh,ow,oh=struct.unpack('>HHHH',p[8:16])
    res[k]={'ew':ew,'eh':eh,'ow':ow,'oh':oh,'ulen':ulen,'csize':v['size'],'ctype':comp_type,'ver':ver}
json.dump(res,open(S+'pkm.json','w'))
print(len(res),magic,ptype)
# relation between e/o
rel=collections.Counter()
for k,r in res.items():
    rel[( 'eh=2oh' if abs(r['eh']-2*r['oh'])<4 else ('eh==oh' if r['eh']==r['oh'] else 'other'), 'ew==ow' if r['ew']==r['ow'] else 'ew!=ow')]+=1
print(rel)
# check ulen == 16 + ew*eh/2
ok=sum(1 for r in res.values() if r['ulen']==16+r['ew']*r['eh']//2)
print('ulen consistent',ok)
ex=[(k,r) for k,r in list(res.items())[:8]]
for k,r in ex: print(k,r)
