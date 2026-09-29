import json, collections, struct, re
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
class R:
    def __init__(s,b): s.b=b; s.p=0; s.bit=0
    def getbit(s):
        v=(s.b[s.p]>>s.bit)&1; s.bit+=1
        if s.bit>=8: s.bit=0; s.p+=1
        return v
    def align(s):
        if s.bit: s.bit=0; s.p+=1
    def rint(s,signed=False):
        n=0
        while not s.getbit(): n+=1
        cur=0
        for a in range(n-1,-1,-1):
            if s.getbit(): cur|=1<<a
        cur|=1<<n
        s.align()
        if signed:
            s_=cur%2
            num=(cur//2) if s_ else -(cur//2)
        else: num=cur-1
        return num
    def rbyte(s): v=s.b[s.p]; s.p+=1; return v
    def rbool(s): return s.rbyte()!=0
    def rutf(s):
        n=(s.b[s.p]<<8)|s.b[s.p+1]; s.p+=2
        v=s.b[s.p:s.p+n].decode('utf-8','replace'); s.p+=n; return v
    def rfloat(s):
        t=s.rbyte()
        if t==0: return 0.0
        if t==1: return 1.0
        if t==2: return -1.0
        if t==3: return 0.5
        if t==4: return float(s.rint(True))
        v=struct.unpack('<f',s.b[s.p:s.p+4])[0]; s.p+=4; return v
    def cstr(s): return s.strings[s.rint(False)]

# property types for CCB v5 (cocos2d-x 2.1)
PT=['position','size','point','pointLock','scaleLock','degrees','integer','float','floatVar','check','spriteFrame','texture','byte','color3','color4fVar','flip','blendmode','fntFile','text','fontTTF','integerLabeled','block','animation','ccbFile','string','blockCCControl','floatScale','floatXY']
stats={'classes':collections.Counter(),'classfiles':collections.Counter(),'props':collections.Counter(),'fonts':collections.Counter(),'seqs':[], 'kf_props':collections.Counter(),'files_anim':0,'nodes':0,'ccbfile':0,'errors':[] ,'frames':collections.Counter(),'blend':collections.Counter(),'texts':[]}
def parse_file(k):
    b=open(idx[k]['path'],'rb').read()
    r=R(b)
    assert b[:4]==b'ibcc'; r.p=4
    ver=r.rint(False)
    js=r.rbool()
    n=r.rint(False)
    r.strings=[r.rutf() for _ in range(n)]
    nseq=r.rint(False); seqs=[]
    for _ in range(nseq):
        dur=r.rfloat(); name=r.cstr(); sid=r.rint(False); chained=r.rint(True)
        # v5: callback channel + sound channel
        for ch in range(2):
            nk=r.rint(False)
            for _ in range(nk):
                t=r.rfloat()
                if ch==0:
                    r.cstr(); r.rint(False)  # callback name, type
                else:
                    r.cstr(); r.rfloat(); r.rfloat(); r.rfloat()  # sound
        seqs.append((name,dur))
    autoplay=r.rint(True)
    seen=set()
    def node():
        cls=r.cstr()
        stats['nodes']+=1; stats['classes'][cls]+=1; seen.add(cls)
        mt=r.rint(False)
        if mt: r.cstr()
        # animated properties
        nseqk=r.rint(False)
        animprops=set()
        for _ in range(nseqk):
            sid=r.rint(False); np_=r.rint(False)
            for _ in range(np_):
                pname=r.cstr(); ptype=r.rint(False); animprops.add(pname); stats['kf_props'][pname]+=1
                nk=r.rint(False)
                for _ in range(nk):
                    t=r.rfloat(); easing=r.rint(False)
                    if easing in (2,3,4,5,6,7): r.rfloat()
                    # value by type
                    pt=PT[ptype]
                    if pt=='check': r.rbool()
                    elif pt=='byte': r.rbyte()
                    elif pt=='color3': r.rbyte();r.rbyte();r.rbyte()
                    elif pt=='degrees': r.rfloat()
                    elif pt in('scaleLock','position','floatXY'):
                        r.rfloat(); r.rfloat()
                        if pt!='floatXY' and False: pass
                    elif pt=='spriteFrame': r.cstr(); r.cstr()
                    else: raise Exception('kf type '+pt)
        # custom class
        if cls and False: pass
        nreg=r.rint(False); ncust=r.rint(False)
        for i in range(nreg+ncust):
            ptype=r.rint(False); pname=r.cstr(); plat=r.rbyte()
            stats['props'][pname]+=1
            pt=PT[ptype]
            if pt=='position': r.rfloat(); r.rfloat(); r.rint(False)
            elif pt=='size': r.rfloat(); r.rfloat(); r.rint(False)
            elif pt=='point' or pt=='pointLock': r.rfloat(); r.rfloat()
            elif pt=='scaleLock': r.rfloat(); r.rfloat(); r.rint(False)
            elif pt in ('degrees','float','floatScale'):
                r.rfloat()
                if pt=='floatScale': r.rint(False)
            elif pt=='floatXY': r.rfloat(); r.rfloat()
            elif pt=='floatVar': r.rfloat(); r.rfloat()
            elif pt in ('integer','integerLabeled'): r.rint(True)
            elif pt=='check': r.rbool()
            elif pt=='spriteFrame':
                sheet=r.cstr(); fr=r.cstr(); stats['frames'][(sheet,fr)]+=1
            elif pt=='texture': r.cstr()
            elif pt=='byte': r.rbyte()
            elif pt=='color3': r.rbyte();r.rbyte();r.rbyte()
            elif pt=='color4fVar':
                for _ in range(8): r.rfloat()
            elif pt=='flip': r.rbool(); r.rbool()
            elif pt=='blendmode': a=r.rint(False); bb=r.rint(False); stats['blend'][(a,bb)]+=1
            elif pt=='fntFile': stats['fonts']['fnt:'+r.cstr()]+=1
            elif pt=='fontTTF': stats['fonts'][r.cstr()]+=1
            elif pt=='text' or pt=='string':
                t=r.cstr()
                if pt=='text' and t: stats['texts'].append(t)
            elif pt=='block':
                sel=r.cstr(); tgt=r.rint(False); x1=r.rint(False); x2=r.rbyte(); stats.setdefault('blockx',collections.Counter())[(x1,x2)]+=1
            elif pt=='blockCCControl':
                sel=r.cstr(); tgt=r.rint(False); r.rint(False)
            elif pt=='ccbFile': r.cstr(); stats['ccbfile']+=1
            elif pt=='animation': r.cstr(); r.cstr()
            else: raise Exception('type '+pt)
        nch=r.rint(False)
        for _ in range(nch): node()
    node()
    for c in seen: stats['classfiles'][c]+=1
    return ver,seqs
files=sorted(k for k in idx if k.endswith('.ccbi') and k.startswith('interface/1024x768/'))
vers=collections.Counter()
for k in files:
    try:
        v,seqs=parse_file(k); vers[v]+=1
        stats['seqs'].append((k,seqs))
        if any(d>0 for _,d in seqs): stats['files_anim']+=1
    except Exception as e:
        stats['errors'].append((k,repr(e)[:120]))
print('files',len(files),'versions',vers,'errors',len(stats['errors']),stats['errors'][:5])
print('nodes',stats['nodes'])
print('classes',stats['classes'].most_common())
print('class->files',stats['classfiles'].most_common())
print('fonts',stats['fonts'].most_common())
print('blend',stats['blend'])
print('keyframed props',stats['kf_props'].most_common())
print('files with timelines of duration>0:',stats['files_anim'])
seqnames=collections.Counter(n for _,s in stats['seqs'] for n,d in s if d>0)
print('timeline names',seqnames.most_common(15))
print('ccbFile refs',stats['ccbfile'])
sheets=collections.Counter(s for (s,f) in stats['frames'])
print('sprite sheets used',len(sheets),sheets.most_common(12))
print('frames used',len(stats['frames']))
tx=stats['texts']; print('static texts',len(tx), [t for t in tx if '<' in t][:10], tx[:20])
print('block extra',stats.get('blockx'));print('top props',stats['props'].most_common(40))
