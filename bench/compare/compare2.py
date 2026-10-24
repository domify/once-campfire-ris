import re, sys, os, json, hashlib
sys.argv=['x']; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'compare.py')).read().split("same = diff = 0")[0])
urls=set()
for p in paths:
    s,h,bd=a("GET",p)
    urls |= set(re.findall(r'(?:src|href)="(/(?:assets|rails/active_storage)/[^"]+)"', bd.decode('utf-8','replace')))
print(len(urls),'asset/blob urls', file=sys.stderr)
bad=0
for u in sorted(urls):
    u=u.replace('&amp;','&')
    ra=a('GET',u); rb=b('GET',u)
    la=ra[1].get('location','').replace('4401','X'); lb=rb[1].get('location','').replace('4402','X')
    ka=('content-type','cache-control','content-disposition','etag')
    if ra[0]!=rb[0] or ra[2]!=rb[2] or la!=lb or any(ra[1].get(k)!=rb[1].get(k) for k in ka):
        bad+=1; print('DIFF',u[:120],ra[0],rb[0],len(ra[2]),len(rb[2]),la[:60],lb[:60],[ (k,ra[1].get(k),rb[1].get(k)) for k in ka if ra[1].get(k)!=rb[1].get(k)])
print('assets/blobs differ',bad,'of',len(urls))
# bot API
key=L['bot_keys.bender']; R=L['rooms.watercooler']
for m,p,d in [('POST',f'/rooms/{R}/{key}/messages',None),('GET',f'/rooms/{R}/{key}/messages',None),('POST',f'/rooms/{R}/bad-key/messages',None)]:
    ra=anon_a(m,p,d,{'Content-Type':'text/plain'}) ; rb=anon_b(m,p,d,{'Content-Type':'text/plain'})
    print('BOT',m,p[-30:],ra[0],rb[0],'same' if ra[2]==rb[2] else ('body',ra[2][:80],rb[2][:80]))
