import os
import re,os,sys,hashlib
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'compare.py')).read().split("same = diff = 0")[0])
urls=set()
for p in paths:
    urls |= set(re.findall(r'"(/rails/active_storage/(?:blobs|representations)/redirect/[^"]+)"', a('GET',p)[2].decode('utf-8','replace')))
bad=0
for u in sorted(urls):
    u=u.replace('&amp;','&'); res=[]
    for c,port in ((a,4401),(b,4402)):
        s,h,body=c('GET',u); n=0
        while s in (301,302) and n<4:
            loc=h['location'].split(f'localhost:{port}')[-1]; s,h,body=c('GET',loc); n+=1
        res.append((s,hashlib.sha1(body).hexdigest()[:10],len(body),h.get('content-type'),h.get('content-disposition'),h.get('cache-control')))
    if res[0]!=res[1]: bad+=1; print('DIFF',u[60:110],res)
print('blobs followed:',len(urls),'differ',bad)
