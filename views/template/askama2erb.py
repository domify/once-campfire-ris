"""Askama (the Rust port's templates) to ris ERB, mechanically; the result is reviewed by hand."""
import re, sys

def expr(e):
    e = e.strip()
    e = re.sub(r'\bh::routes::(\w+)\(\)', r'\1_path', e)
    e = re.sub(r'\bh::routes::(\w+)\(', r'\1_path(', e)
    e = e.replace('h::attrs()', 'attrs').replace('h::', '').replace('crate::', '')
    e = re.sub(r'\.(aria_hidden|autofocus|hidden|readonly|empty|is_empty)\(\)', lambda m: '.' + {'is_empty': 'empty?'}.get(m.group(1), m.group(1)), e)
    e = e.replace('.type_(', '.type(').replace('.as_str()', '').replace('.as_deref()', '').replace('.clone()', '').replace('.to_string()', '')
    e = re.sub(r'\bSome\((.*?)\)', r'\1', e)
    e = re.sub(r'\bNone\b', 'nil', e)
    e = re.sub(r'&(\w)', r'\1', e)
    e = re.sub(r'\*(\w)', r'\1', e)
    e = e.replace('.is_some()', '').replace('self.', '')
    e = re.sub(r'(\w+)\.is_(\w+)\(\)', r'\1.\2?', e)
    e = re.sub(r'"\s*~\s*', '" + ', e).replace(' ~ ', ' + ')
    return e

def stmt(s, ws):
    s = s.strip()
    m = re.match(r'(el)?if (let Some\((\w+)\) = )?(.*)', s)
    if s.startswith('elif '):
        return 'elsif ' + expr(s[5:])
    if m and s.startswith('if '):
        if m.group(2):
            return 'if %s = %s' % (m.group(3), expr(m.group(4)))
        return 'if ' + expr(m.group(4))
    if s in ('endif', 'endfor', 'endfilter', 'endblock', 'endmatch', 'endwhen'):
        return 'end'
    if s == 'else':
        return 'else'
    m = re.match(r'for (\w+) in (.*)', s)
    if m:
        return '%s.each do |%s|' % (expr(m.group(2)), m.group(1))
    m = re.match(r'let (\w+) = (.*)', s)
    if m:
        return '%s = %s' % (m.group(1), expr(m.group(2)))
    m = re.match(r'include "(.*?)\.html"', s)
    if m:
        return 'include "%s.html.erb"' % m.group(1)
    m = re.match(r'filter (\w+)\((.*)\)', s)
    if m:
        return '__FILTER__ %s(%s)' % (m.group(1), expr(m.group(2)))
    m = re.match(r'block (\w+)', s)
    if m:
        return '__BLOCK__ ' + m.group(1)
    return '__TODO__ ' + s

def convert(text):
    out = []
    pos = 0
    for m in re.finditer(r'\{([{%#])(-?)(.*?)(-?)([}%#])\}', text, re.S):
        out.append(text[pos:m.start()])
        kind, lt, body, rt = m.group(1), m.group(2), m.group(3), m.group(4)
        l = '<%-' if lt else '<%'
        r = '-%>' if rt else '%>'
        if kind == '{':
            out.append('%s= %s %s' % (l, expr(body), r))
        elif kind == '#':
            out.append('%s#%s%s' % (l, body.rstrip('-'), r))
        else:
            st = stmt(body, None)
            if st.startswith('__FILTER__ '):
                out.append('%s= %s do %s' % (l, st[11:], r))
            elif st.startswith('__BLOCK__'):
                out.append('%s content_for "%s" do %s' % (l, st.split()[1], r))
            else:
                out.append('%s %s %s' % (l, st, r))
        pos = m.end()
    out.append(text[pos:])
    return ''.join(out)

src, dst, header = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(src).read()
text = re.sub(r'^\{#-?.*?-?#\}\n?', '', text, count=1, flags=re.S)
open(dst, 'w').write('<%# ' + header + ' -%>\n' + convert(text))
