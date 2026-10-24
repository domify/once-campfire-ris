import json, sys, urllib.request, urllib.parse, http.cookiejar, re, difflib, os
L = json.load(open(os.path.expanduser('~/contribute/once-campfire-verification/fixtures/default/labels.json')))
PW = os.environ['VERIFICATION_PASSWORD']
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
def client(port, email):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
    base = f'http://localhost:{port}'
    def req(method, path, data=None, headers={}):
        body = urllib.parse.urlencode(data).encode() if data else None
        r = urllib.request.Request(base+path, data=body, method=method, headers={'Sec-Fetch-Site':'same-origin','Origin':base, **headers})
        try: resp = op.open(r)
        except urllib.error.HTTPError as e: resp = e
        return resp.status, {k.lower():v for k,v in resp.headers.items()}, resp.read()
    if email: print(port, 'login', req('POST','/session',{'email_address':email,'password':PW})[0], file=sys.stderr)
    return req
def norm(b, port):
    s = b.decode('utf-8','replace').replace(f'localhost:{port}','HOST')
    s = re.sub(r'<meta name="csrf-param"[^>]*>\s*<meta name="csrf-token"[^>]*>','',s)
    s = re.sub(r'name="authenticity_token" value="[^"]*"','tok',s)
    return s
R, D = L['rooms.'+'hq'], L
paths = ['/', '/session/new', '/first_run', f'/rooms/{R}', f'/rooms/{R}/messages', f'/rooms/{R}/messages?before={L["messages.busy_060"]}',
 f'/rooms/{L["rooms.watercooler"]}', f'/rooms/{L["rooms.designers"]}', f'/rooms/{L["rooms.david_and_jason"]}', '/rooms/opens/new','/rooms/closeds/new','/rooms/directs/new',
 f'/rooms/{R}/edit', f'/rooms/{R}/involvement', f'/rooms/{R}/settings', '/searches?q=pizza', '/searches', '/account/edit', '/account/users', '/account/bots', '/account/bots/new',
 f'/account/bots/{L["users.bender"]}/edit', '/account/join_code', '/account/logo', '/account/custom_styles/edit', f'/users/{L["users.jason"]}', f'/users/{L["users.david"]}/avatar',
 '/users/me/profile', '/users/me/sidebar', '/users/me/push_subscriptions', f'/autocompletable/users?query=j', f'/autocompletable/users.json?query=j', '/webmanifest', '/service-worker.js', '/up',
 f'/messages/{L["messages.first"]}/boosts', f'/rooms/{R}/@{L["messages.first"]}', f'/join/{L["join_codes.signal"]}', f'/session/transfers/{L["transfers.david"]}', '/nope', '/qr_code/aGVsbG8']
paths += [f'/rooms/{R}/messages/{L["messages."+m]}' for m in ['plain','code','table','formatting','mention','image','video','file','opengraph','emoji','long','edited']]
a, b = client(4401, L['emails.david']), client(4402, L['emails.david'])
anon_a, anon_b = client(4401,None), client(4402,None)
same = diff = 0
for p in paths + ['ANON '+x for x in ['/', '/session/new', f'/rooms/{R}', '/up', f'/join/{L["join_codes.signal"]}']]:
    ca, cb = (anon_a, anon_b) if p.startswith('ANON ') else (a, b)
    q = p.removeprefix('ANON ')
    sa, ha, ba = ca('GET', q); sb, hb, bb = cb('GET', q)
    na, nb = norm(ba,4401), norm(bb,4402)
    la, lb = ha.get('location','').replace('4401','X'), hb.get('location','').replace('4402','X')
    ct = (ha.get('content-type'), hb.get('content-type'))
    ok = sa==sb and na==nb and la==lb and ct[0]==ct[1]
    same += ok; diff += not ok
    wsonly = not ok and sa==sb and re.sub(r'\s+','',na)==re.sub(r'\s+','',nb)
    if wsonly: print('WS  ', p); continue
    if not ok:
        print(f'DIFF {p}: status {sa}/{sb} type {ct} loc {la!r}/{lb!r} bytes {len(ba)}/{len(bb)}')
        if na!=nb:
            for l in list(difflib.unified_diff(na.splitlines(), nb.splitlines(), 'rust','ris', n=0, lineterm=''))[2:40]: print('   ', l[:200])
print(f'same {same}, differ {diff}')
