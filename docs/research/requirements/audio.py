import json, collections, struct, subprocess, re
S='docs/research/requirements/'
idx=json.load(open(S+'index.json'))
aud=[k for k in idx if k.endswith('.wav') or k.endswith('.mp3')]
by=collections.defaultdict(lambda:[0,0,0.0]); fmt=collections.Counter(); rows=[]
for k in aud:
    folder=k.split('/')[0]+('/'+k.split('/')[1] if k.startswith('music/') and k.count('/')>1 else '')
    ext=k.rsplit('.',1)[1]
    out=subprocess.run(['afinfo',idx[k]['path']],capture_output=True,text=True).stdout
    dur=re.search(r'estimated duration: ([\d.]+)',out); dur=float(dur.group(1)) if dur else 0
    f=re.search(r'Data format:\s+(.*)',out); f=f.group(1).strip() if f else '?'
    br=re.search(r'bit rate: (\d+)',out)
    f=re.sub(r'\s+',' ',f)
    fmt[(ext,f)]+=1
    b=by[(folder,ext)]; b[0]+=1; b[1]+=idx[k]['size']; b[2]+=dur
    rows.append((k,ext,f,dur,idx[k]['size']))
json.dump(rows,open(S+'audio.json','w'))
print('audio files',len(aud),'total MB',round(sum(idx[k]['size'] for k in aud)/1e6,1))
for (fo,e),(n,sz,d) in sorted(by.items()): print(f'  {fo:14s} {e}: n={n:3d} size={sz/1e6:6.1f} MB  dur={d/60:6.1f} min')
for f,c in fmt.most_common(): print('  ',c,f)
print('longest',sorted(rows,key=lambda r:-r[3])[:5])
