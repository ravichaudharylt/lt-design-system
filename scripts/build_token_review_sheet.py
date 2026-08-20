"""Review sheet for ALL non-design-canonical --lt-* tokens (the "orphans").

Design canonicals (declared in tokens.css minus known orphans) are EXCLUDED.
Everything else defined in tokens.css is in scope: --lt-c-* value-encoded tokens
AND semantic-named non-canonical tokens (--lt-text-teal-43b, --lt-bg-emphasis, ...).

One row per *usage*. Columns:
  token, kind (c-token|semantic), hex, total_refs, file, line, context,
  usage_type, css_class, class_state, file_reachable, suggested_action
"""
import os, re, json, collections

WP = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-web-platform-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-components-dark-mode'
TOKENS_CSS = os.environ.get('TOKENS_CSS', f'{LTC}/src/styles/tokens.css')
OUT = '/Users/ravichaudhary/Desktop/LambdaTest/dark-mode-reports/token_review.html'
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')

# --- design canonical set (to EXCLUDE) = declared in tokens.css minus known orphans
# (data/orphan_tokens.json mirrors col A of the Design Team Review sheet) ---
with open(os.path.join(DATA, 'orphan_tokens.json')) as fh:
    ORPHAN_TOKENS = set(json.load(fh))
with open(TOKENS_CSS) as fh:
    design_set = set(re.findall(r'(--lt-[a-zA-Z0-9-]+)\s*:', fh.read())) - ORPHAN_TOKENS

# --- all tokens defined in tokens.css (light block hex) ---
tok_hex = {}
content = open(TOKENS_CSS).read()
for m in re.finditer(r'(--lt-[a-zA-Z0-9-]+)\s*:\s*([^;]+);', content):
    tok_hex.setdefault(m.group(1), m.group(2).strip())

# scope = defined tokens minus design canonicals
scope = set(tok_hex) - design_set
print(f"Tokens defined: {len(tok_hex)}  |  design canonicals: {len(design_set)}  |  in scope (orphans): {len(scope)}")

# --- reachability (reuse v3) ---
reachable = set()
try:
    reachable = set(json.load(open('/tmp/reachability_v3.json'))['reachable'])
except Exception:
    print("  ! /tmp/reachability_v3.json missing — file_reachable will be blank")

# --- CSS-module class consumption map ---
class_consumed = collections.Counter()
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dp, dns, fns in os.walk(root):
        if any(p in dp for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dns[:] = []; continue
        for fn in fns:
            if not fn.endswith(('.tsx','.ts','.jsx','.js')): continue
            try: c = open(os.path.join(dp, fn)).read()
            except: continue
            for m in re.finditer(r'(?:styles?|cn|cls|css)\s*\.\s*([a-zA-Z_]\w+)', c):
                class_consumed[m.group(1)] += 1
            for m in re.finditer(r'(?:styles?|cn|cls|css)\s*\[\s*["\']([a-zA-Z_]\w+)["\']', c):
                class_consumed[m.group(1)] += 1

TOKEN_USE_RE = re.compile(r'var\((--lt-[a-zA-Z0-9-]+)\)')

def classify_usage(path, line):
    is_css = path.endswith(('.css','.scss','.module.css'))
    if 'text-[' in line or 'bg-[' in line or 'border-[' in line or '-[color:' in line:
        return 'tailwind'
    if re.search(r'\b(fill|stroke|stopColor|stop-color|flood-color)\s*[=:]', line):
        return 'svg-attr'
    if is_css:
        return 'scss-prop' if path.endswith('.scss') else 'css-prop'
    return 'js-inline'

def css_class_for_line(lines, idx):
    depth = 0
    for j in range(idx, -1, -1):
        l = lines[j]
        depth += l.count('}') - l.count('{')
        m = re.match(r'\s*\.([a-zA-Z_][\w-]*)', l)
        if m and '{' in l and depth <= 0:
            return m.group(1)
    return ''

records = []
ref_count = collections.Counter()
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dp, dns, fns in os.walk(root):
        if any(p in dp for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dns[:] = []; continue
        for fn in fns:
            if not fn.endswith(('.tsx','.ts','.jsx','.js','.css','.scss','.html')): continue
            path = os.path.join(dp, fn)
            if path == TOKENS_CSS: continue
            try: lines = open(path).read().splitlines()
            except: continue
            is_css = path.endswith(('.css','.scss','.module.css'))
            is_mod = path.endswith('.module.css')
            for idx, line in enumerate(lines):
                for m in TOKEN_USE_RE.finditer(line):
                    tok = m.group(1)
                    if tok not in scope: continue
                    ref_count[tok] += 1
                    cls = ''; cstate = ''
                    if is_css:
                        cls = css_class_for_line(lines, idx)
                        if is_mod and cls:
                            cstate = 'consumed' if class_consumed.get(cls,0) > 0 else 'DEAD-class'
                        elif cls:
                            cstate = 'global-class'
                    records.append({
                        'token': tok,
                        'kind': 'c-token' if tok.startswith('--lt-c-') else 'semantic',
                        'hex': tok_hex.get(tok,'?'),
                        'file': path.replace(WP+'/','').replace(LTC+'/','lt-components/'),
                        'line': idx+1,
                        'context': line.strip()[:160],
                        'usage_type': classify_usage(path, line),
                        'css_class': cls,
                        'class_state': cstate,
                        'reachable': 'LIVE' if path in reachable else 'unreachable',
                    })

for r in records:
    r['total_refs'] = ref_count[r['token']]
    if r['class_state'] == 'DEAD-class':
        r['suggest'] = 'revert dead class to upstream'
    elif r['reachable'] != 'LIVE':
        r['suggest'] = 'in dead-code file - revert to upstream'
    elif r['kind'] == 'c-token':
        r['suggest'] = 'LIVE c-token - decision: semantic token? brand? revert?'
    else:
        r['suggest'] = 'LIVE semantic non-canonical - map to canonical or revert?'

records.sort(key=lambda r: (r['total_refs'], r['token'], r['file'], r['line']))

# tokens with ZERO usages anywhere (pure orphans in tokens.css)
zero_ref_tokens = sorted(scope - set(ref_count))

tokens_used = sorted(set(r['token'] for r in records))
n_c = len(set(r['token'] for r in records if r['kind']=='c-token'))
n_sem = len(set(r['token'] for r in records if r['kind']=='semantic'))
n_dead_class = sum(1 for r in records if r['class_state']=='DEAD-class')
n_unreach = sum(1 for r in records if r['reachable']!='LIVE')

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

rows_html = []
# include zero-ref tokens as their own rows at the very top
for tok in zero_ref_tokens:
    hx = tok_hex.get(tok,'?')
    sw = f'<span class="sw" style="background:{esc(hx)}"></span>' if hx.startswith('#') else ''
    kind = 'c-token' if tok.startswith('--lt-c-') else 'semantic'
    rows_html.append(
        f'<tr class="zero" data-token="{esc(tok)}" data-type="" data-state="zero" data-kind="{kind}">'
        f'<td class="mono">{esc(tok)}</td><td>{kind}</td>'
        f'<td class="mono">{sw}{esc(hx)}</td><td class="num">0</td>'
        f'<td class="file">&mdash;</td><td class="num">&mdash;</td>'
        f'<td class="ctx">(no usages — pure orphan in tokens.css)</td>'
        f'<td>&mdash;</td><td>&mdash;</td><td>&mdash;</td><td>&mdash;</td>'
        f'<td>delete from tokens.css</td></tr>'
    )
for r in records:
    state_cls = ('dead' if r['class_state']=='DEAD-class'
                 else 'unreach' if r['reachable']!='LIVE' else 'live')
    hx = r['hex']
    sw = f'<span class="sw" style="background:{esc(hx)}"></span>' if hx.startswith('#') else ''
    rows_html.append(
        f'<tr class="{state_cls}" data-token="{esc(r["token"])}" data-type="{esc(r["usage_type"])}" '
        f'data-state="{state_cls}" data-kind="{esc(r["kind"])}">'
        f'<td class="mono">{esc(r["token"])}</td>'
        f'<td>{esc(r["kind"])}</td>'
        f'<td class="mono">{sw}{esc(hx)}</td>'
        f'<td class="num">{r["total_refs"]}</td>'
        f'<td class="file">{esc(r["file"])}</td>'
        f'<td class="num">{r["line"]}</td>'
        f'<td class="ctx mono">{esc(r["context"])}</td>'
        f'<td>{esc(r["usage_type"])}</td>'
        f'<td class="mono">{esc(r["css_class"])}</td>'
        f'<td>{esc(r["class_state"])}</td>'
        f'<td>{esc(r["reachable"])}</td>'
        f'<td>{esc(r["suggest"])}</td></tr>'
    )

html = f'''<!doctype html><html><head><meta charset="utf-8">
<title>Orphan Token Review (non-design-canonical)</title>
<style>
 body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 16px; color: #1f2328; }}
 h1 {{ font-size: 18px; margin: 0 0 4px; }}
 .sub {{ color: #656d76; font-size: 12px; margin-bottom: 12px; }}
 .stats {{ display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }}
 .pill {{ background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 6px 12px; font-size: 12px; }}
 .pill b {{ font-size: 16px; display: block; }}
 .controls {{ margin-bottom: 10px; font-size: 12px; }}
 input, select {{ font-size: 12px; padding: 3px 6px; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 11px; }}
 th, td {{ border: 1px solid #d0d7de; padding: 3px 6px; text-align: left; vertical-align: top; }}
 th {{ background: #f6f8fa; position: sticky; top: 0; cursor: pointer; }}
 td.mono, .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
 td.num {{ text-align: right; }}
 td.file {{ max-width: 320px; word-break: break-all; }}
 td.ctx {{ max-width: 440px; word-break: break-all; color: #4a4a4a; }}
 tr.dead {{ background: #fff1f0; }}
 tr.unreach {{ background: #fffbe6; }}
 tr.live {{ background: #fff; }}
 tr.zero {{ background: #f0f0ff; }}
 .sw {{ display: inline-block; width: 10px; height: 10px; border: 1px solid #aaa; margin-right: 4px; vertical-align: middle; }}
 .legend span {{ margin-right: 12px; }}
</style></head><body>
<h1>Orphan Token Review &mdash; non-design-canonical --lt-* tokens</h1>
<div class="sub">One row per usage. Design canonicals ({len(design_set)}) excluded. Generated for review &mdash; no changes applied. Sorted by ref count.</div>
<div class="stats">
 <div class="pill"><b>{len(scope)}</b> orphan tokens in scope</div>
 <div class="pill"><b>{n_c}</b> --lt-c-* (value-encoded)</div>
 <div class="pill"><b>{n_sem}</b> semantic-named non-canonical</div>
 <div class="pill"><b>{len(zero_ref_tokens)}</b> zero-ref (pure orphan)</div>
 <div class="pill"><b>{len(records)}</b> total usages</div>
 <div class="pill"><b>{n_dead_class}</b> usages in DEAD css classes</div>
 <div class="pill"><b>{n_unreach}</b> usages in unreachable files</div>
</div>
<div class="controls legend">
 <span>Token: <input id="fTok" oninput="flt()" placeholder="--lt-..."></span>
 <span>Kind: <select id="fKind" onchange="flt()"><option value="">all</option>
   <option>c-token</option><option>semantic</option></select></span>
 <span>Type: <select id="fType" onchange="flt()"><option value="">all</option>
   <option>css-prop</option><option>scss-prop</option><option>js-inline</option>
   <option>tailwind</option><option>svg-attr</option></select></span>
 <span>State: <select id="fState" onchange="flt()"><option value="">all</option>
   <option value="zero">zero-ref</option><option value="live">live</option>
   <option value="dead">dead-class</option><option value="unreach">unreachable</option></select></span>
 <span class="legend" style="margin-left:12px;">
   <span style="background:#f0f0ff;padding:1px 6px;">zero-ref</span>
   <span style="background:#fff;border:1px solid #ccc;padding:1px 6px;">live</span>
   <span style="background:#fff1f0;padding:1px 6px;">dead class</span>
   <span style="background:#fffbe6;padding:1px 6px;">unreachable file</span>
 </span>
</div>
<table id="tbl"><thead><tr>
 <th onclick="sortT(0)">Token</th><th onclick="sortT(1)">Kind</th><th onclick="sortT(2)">Hex</th>
 <th onclick="sortT(3)">Refs</th><th onclick="sortT(4)">File</th><th onclick="sortT(5)">Line</th>
 <th>Context</th><th onclick="sortT(7)">Usage type</th><th onclick="sortT(8)">CSS class</th>
 <th onclick="sortT(9)">Class state</th><th onclick="sortT(10)">File reach</th>
 <th>Suggested action (review)</th>
</tr></thead><tbody>
{chr(10).join(rows_html)}
</tbody></table>
<script>
 function flt() {{
   var t = document.getElementById('fTok').value.toLowerCase();
   var k = document.getElementById('fKind').value;
   var ty = document.getElementById('fType').value;
   var st = document.getElementById('fState').value;
   document.querySelectorAll('#tbl tbody tr').forEach(function(tr) {{
     var okT = !t || tr.dataset.token.toLowerCase().includes(t);
     var okK = !k || tr.dataset.kind === k;
     var okTy = !ty || tr.dataset.type === ty;
     var okS = !st || tr.dataset.state === st;
     tr.style.display = (okT && okK && okTy && okS) ? '' : 'none';
   }});
 }}
 function sortT(col) {{
   var tb = document.querySelector('#tbl tbody');
   var rows = Array.from(tb.rows);
   var asc = tb.dataset.sortCol != col || tb.dataset.sortDir != 'asc';
   rows.sort(function(a,b) {{
     var x = a.cells[col].innerText, y = b.cells[col].innerText;
     var nx = parseFloat(x), ny = parseFloat(y);
     if (!isNaN(nx) && !isNaN(ny)) {{ x = nx; y = ny; }}
     return (x<y?-1:x>y?1:0) * (asc?1:-1);
   }});
   rows.forEach(function(r) {{ tb.appendChild(r); }});
   tb.dataset.sortCol = col; tb.dataset.sortDir = asc ? 'asc' : 'desc';
 }}
</script>
</body></html>'''

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w').write(html)
print(f"Usages: {len(records)}  |  zero-ref tokens: {len(zero_ref_tokens)}")
print(f"  c-token: {n_c}  semantic: {n_sem}")
print(f"  DEAD css-class usages: {n_dead_class}  |  unreachable-file usages: {n_unreach}")
print(f"Sheet: {OUT}")
