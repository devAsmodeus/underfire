import json, sys
C=json.load(open('data/config.json'))
def show(n,ind=0,maxch=40,depth=6):
    a=' '.join(f'{k}="{v}"' for k,v in (n.get('attr') or {}).items())
    t=(n.get('text') or '').strip()
    print('  '*ind+f"<{n['tag']} {a}>"+(f" text={t[:80]!r}" if t else ''))
    if depth==0: return
    ch=n.get('children') or []
    for c in ch[:maxch]: show(c,ind+1,maxch,depth-1)
    if len(ch)>maxch: print('  '*(ind+1)+f'... +{len(ch)-maxch}')
if __name__=='__main__':
    sec=sys.argv[1]; i=int(sys.argv[2]) if len(sys.argv)>2 else 0
    mc=int(sys.argv[3]) if len(sys.argv)>3 else 40
    print(sec,len(C[sec]))
    show(C[sec][i],maxch=mc)
