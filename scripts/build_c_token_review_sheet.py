"""Build a review sheet for all --lt-c-* tokens.

One row per *usage* (a token with 3 refs => 3 rows). Columns:
  token, hex, total_refs, file, line, context, usage_type, css_class,
  class_consumed, file_reachable, suggested_action

usage_type:  css-prop | scss-prop | js-inline | tailwind | svg-attr | other
class_consumed: only meaningful for CSS-module classes — is `.class` used via styles.class?
file_reachable: LIVE if file is reachable from an app entry (BFS v3)
suggested_action: a heuristic hint for review, NOT applied automatically
"""
import os, re, json, collections

WP = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-web-platform-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-components-dark-mode'
TOKENS_CSS = os.environ.get('TOKENS_CSS', f'{LTC}/src/styles/tokens.css')
OUT = '/Users/ravichaudhary/Desktop/LambdaTest/dark-mode-reports/c_token_review.html'

# --- token hex values from tokens.css (light block) ---
tok_hex = {}
content = open(TOKENS_CSS).read()
for m in re.finditer(r'(--lt-c-[a-zA-Z0-9-]+)\s*:\s*([^;]+);', content):
    tok_hex.setdefault(m.group(1), m.group(2).strip())

# --- reachability set (reuse v3 if present, else empty) ---
reachable = set()
try:
    reachable = set(json.load(open('/tmp/reachability_v3.json'))['reachable'])
except Exception:
    pass

# --- CSS-module class consumption map (styles.X / styles['X']) ---
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

# --- walk source, collect one record per --lt-c-* usage ---
TOKEN_USE_RE = re.compile(r'var\((--lt-c-[a-zA-Z0-9-]+)\)')
records = []
ref_count = collections.Counter()

def classify_usage(path, line):
    is_css = path.endswith(('.css','.scss','.module.css'))
    if 'text-[' in line or 'bg-[' in line or 'border-[' in line or '-[color:' in line:
        return 'tailwind'
    if re.search(r'\b(fill|stroke|stopColor|stop-color|flood-color)\s*[=:]', line):
        return 'svg-attr'
    if is_css:
        return 'scss-prop' if path.endswith('.scss') else 'css-prop'
    # js/ts file, not tailwind, not svg
    return 'js-inline'

def css_class_for_line(lines, idx):
    """Walk upward to find the nearest `.className {` selector for a CSS line."""
    depth = 0
    for j in range(idx, -1, -1):
        l = lines[j]
        depth += l.count('}') - l.count('{')
        m = re.match(r'\s*\.([a-zA-Z_][\w-]*)', l)
        if m and '{' in l and depth <= 0:
            return m.group(1)
    return ''

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
            is_css_module = path.endswith('.module.css')
            for idx, line in enumerate(lines):
                for m in TOKEN_USE_RE.finditer(line):
                    tok = m.group(1)
                    ref_count[tok] += 1
                    utype = classify_usage(path, line)
                    cls = ''
                    consumed = ''
                    if is_css:
                        cls = css_class_for_line(lines, idx)
                        if is_css_module and cls:
                            consumed = 'consumed' if class_consumed.get(cls, 0) > 0 else 'DEAD-class'
                        elif cls:
                            consumed = 'global-class'  # plain .css — global selector
                    records.append({
                        'token': tok,
                        'hex': tok_hex.get(tok, '?'),
                        'file': path.replace(WP+'/','').replace(LTC+'/','lt-components/'),
                        'line': idx+1,
                        'context': line.strip()[:160],
                        'usage_type': utype,
                        'css_class': cls,
                        'class_state': consumed,
                        'reachable': 'LIVE' if path in reachable else 'unreachable',
                    })

# fill total refs + suggested action
for r in records:
    r['total_refs'] = ref_count[r['token']]
    # heuristic suggestion
    if r['class_state'] == 'DEAD-class':
        r['suggest'] = 'revert dead class to upstream'
    elif r['reachable'] != 'LIVE':
        r['suggest'] = 'in dead-code file — revert to upstream'
    else:
        r['suggest'] = 'LIVE — needs decision (semantic token? brand? revert?)'

records.sort(key=lambda r: (r['total_refs'], r['token'], r['file'], r['line']))

# --- counts ---
tokens_all = sorted(set(r['token'] for r in records))
n_live = len(set(r['token'] for r in records if r['reachable']=='LIVE'))
n_dead_class = sum(1 for r in records if r['class_state']=='DEAD-class')
n_unreachable = sum(1 for r in records if r['reachable']!='LIVE')

def esc(s):
    return (str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))

rows_html = []
for r in records:
    state_cls = ''
    if r['class_state'] == 'DEAD-class': state_cls = 'dead'
    elif r['reachable'] != 'LIVE': state_cls = 'unreach'
    else: state_cls = 'live'
    swatch = f'<span class="sw" style="background:{esc(r["hex"])}"></span>' if r['hex'].startswith('#') else ''
    rows_html.append(
        f'<tr class="{state_cls}" data-token="{esc(r["token"])}" data-type="{esc(r["usage_type"])}" '
        f'data-state="{state_cls}">'
        f'<td class="mono">{esc(r["token"])}</td>'
        f'<td class="mono">{swatch}{esc(r["hex"])}</td>'
        f'<td class="num">{r["total_refs"]}</td>'
        f'<td class="file">{esc(r["file"])}</td>'
        f'<td class="num">{r["line"]}</td>'
        f'<td class="ctx mono">{esc(r["context"])}</td>'
        f'<td>{esc(r["usage_type"])}</td>'
        f'<td class="mono">{esc(r["css_class"])}</td>'
        f'<td>{esc(r["class_state"])}</td>'
        f'<td>{esc(r["reachable"])}</td>'
        f'<td>{esc(r["suggest"])}</td>'
        f'</tr>'
    )

html = f'''<!doctype html><html><head><meta charset="utf-8">
<title>--lt-c-* Token Review</title>
<style>
 body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 16px; color: #1f2328; }}
 h1 {{ font-size: 18px; margin: 0 0 4px; }}
 .sub {{ color: #656d76; font-size: 12px; margin-bottom: 12px; }}
 .stats {{ display: flex; gap: 16px; margin-bottom: 12px; flex-wrap: wrap; }}
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
 td.ctx {{ max-width: 460px; word-break: break-all; color: #4a4a4a; }}
 tr.dead {{ background: #fff1f0; }}
 tr.unreach {{ background: #fffbe6; }}
 tr.live {{ background: #fff; }}
 .sw {{ display: inline-block; width: 10px; height: 10px; border: 1px solid #aaa; margin-right: 4px; vertical-align: middle; }}
 .legend span {{ margin-right: 14px; }}
</style></head><body>
<h1>--lt-c-* Token Review Sheet</h1>
<div class="sub">One row per usage. Generated for review &mdash; no changes applied. Sorted by ref count (lowest first).</div>
<div class="stats">
 <div class="pill"><b>{len(tokens_all)}</b> distinct --lt-c-* tokens</div>
 <div class="pill"><b>{len(records)}</b> total usages</div>
 <div class="pill"><b>{n_live}</b> tokens touch LIVE files</div>
 <div class="pill"><b>{n_dead_class}</b> usages in DEAD css-module classes</div>
 <div class="pill"><b>{n_unreachable}</b> usages in unreachable files</div>
</div>
<div class="controls legend">
 <span>Filter token: <input id="fTok" oninput="flt()" placeholder="--lt-c-..."></span>
 <span>Type: <select id="fType" onchange="flt()"><option value="">all</option>
   <option>css-prop</option><option>scss-prop</option><option>js-inline</option>
   <option>tailwind</option><option>svg-attr</option></select></span>
 <span>State: <select id="fState" onchange="flt()"><option value="">all</option>
   <option value="live">live</option><option value="dead">dead-class</option>
   <option value="unreach">unreachable</option></select></span>
 <span class="legend" style="margin-left:16px;">
   <span style="background:#fff;border:1px solid #ccc;padding:1px 6px;">live</span>
   <span style="background:#fff1f0;padding:1px 6px;">dead css class</span>
   <span style="background:#fffbe6;padding:1px 6px;">unreachable file</span>
 </span>
</div>
<table id="tbl"><thead><tr>
 <th onclick="sortT(0)">Token</th><th onclick="sortT(1)">Hex</th><th onclick="sortT(2)">Refs</th>
 <th onclick="sortT(3)">File</th><th onclick="sortT(4)">Line</th><th>Context</th>
 <th onclick="sortT(6)">Usage type</th><th onclick="sortT(7)">CSS class</th>
 <th onclick="sortT(8)">Class state</th><th onclick="sortT(9)">File reach</th>
 <th>Suggested action (review)</th>
</tr></thead><tbody>
{chr(10).join(rows_html)}
</tbody></table>
<script>
 function flt() {{
   var t = document.getElementById('fTok').value.toLowerCase();
   var ty = document.getElementById('fType').value;
   var st = document.getElementById('fState').value;
   document.querySelectorAll('#tbl tbody tr').forEach(function(tr) {{
     var okT = !t || tr.dataset.token.toLowerCase().includes(t);
     var okTy = !ty || tr.dataset.type === ty;
     var okS = !st || tr.dataset.state === st;
     tr.style.display = (okT && okTy && okS) ? '' : 'none';
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
print(f"Tokens: {len(tokens_all)}  |  Usages: {len(records)}")
print(f"  DEAD css-class usages: {n_dead_class}")
print(f"  unreachable-file usages: {n_unreachable}")
print(f"Sheet: {OUT}")
