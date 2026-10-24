import os
import re,os,sys,json,sqlite3,difflib
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'compare.py')).read().split("same = diff = 0")[0])
R=L['rooms.hq']; key=L['bot_keys.bender']
TS={'Accept':'text/vnd.turbo-stream.html, text/html, application/xhtml+xml'}
def n(s,port):
    s=norm(s if isinstance(s,bytes) else s.encode(),port)
    s=re.sub(r'\b9334\d{5}\b|\b\d{9,10}\b','ID',s)
    s=re.sub(r'\d{4}-\d\d-\d\dT[\d:.]+Z','TIME',s)
    s=re.sub(r'(blob_id|data)":\d+','\\1":N',s)
    return s
steps=[('POST',f'/rooms/{R}/messages',{'message[body]':'<div>Hello from the comparison</div>','message[client_message_id]':'abc-123'},TS),
       ('POST',f'/rooms/{R}/messages',{'message[body]':''},TS),
       ('POST',f'/messages/{L["messages.plain"]}/boosts',{'boost[content]':'🎉'},TS),
       ('POST','/rooms/opens',{'room[name]':'Compare room'},{}),
       ('PUT',f'/rooms/{R}/involvement',{'involvement':'mentions'},TS),
       ('POST','/searches',{'q':'hello'},{}),
       ('DELETE','/searches/clear',None,TS),
      ]
for m,p,d,h in steps:
    ra=a(m,p,d,h); rb=b(m,p,d,h)
    la=n(ra[1].get('location',''),4401); lb=n(rb[1].get('location',''),4402)
    ba=n(ra[2],4401); bb=n(rb[2],4402)
    ok=ra[0]==rb[0] and la==lb and ba==bb
    print('OK  ' if ok else 'DIFF',m,p,ra[0],rb[0],la,lb)
    if not ok and ba!=bb:
        for l in list(difflib.unified_diff(ba.splitlines(),bb.splitlines(),'rust','ris',n=0,lineterm=''))[2:14]: print('   ',l[:220])
anon_a,anon_b=client(4401,None),client(4402,None)
ra=anon_a('POST',f'/rooms/{R}/{key}/messages',None,{}); 
import urllib.request
for port in (4401,4402):
    r=urllib.request.Request(f'http://localhost:{port}/rooms/{R}/{key}/messages',data=b'Hi from bot',method='POST',headers={'Content-Type':'text/plain'})
    try: resp=urllib.request.urlopen(r); print('bot post',port,resp.status,resp.read()[:100])
    except urllib.error.HTTPError as e: print('bot post',port,e.code,e.read()[:100])
def dump(path):
    c=sqlite3.connect(path)
    q=lambda sql:[tuple(x) for x in c.execute(sql)]
    return {'messages':q("select r.body, m.creator_id, m.client_message_id from messages m join action_text_rich_texts r on r.record_id=m.id and r.record_type='Message' order by m.id desc limit 3"),
            'boosts':q("select content, booster_id, message_id from boosts order by id desc limit 1"),
            'rooms':q("select name,type,creator_id from rooms order by id desc limit 1"),
            'memberships':q(f"select involvement from memberships where room_id={R} and user_id={L['users.david']}"),
            'searches':q("select query from searches order by id desc limit 3")}
da=dump(os.environ['WORK']+'/rust/storage/db/production.sqlite3'); db=dump(os.environ['WORK']+'/ris/storage/db/production.sqlite3')
for k in da: print('DB  ' + ('same ' if da[k]==db[k] else 'DIFF '),k, '' if da[k]==db[k] else (da[k],db[k]))
