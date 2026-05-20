"""Generate the main token_sheet.html (used as index.html on Pages)."""
import re, os, collections, openpyxl

TOKENS_CSS = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components/src/styles/tokens.css'
WP = '/Users/ravichaudhary/Desktop/LambdaTest/lt-web-platform-worktrees/feat-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components'
XLSX = '/Users/ravichaudhary/Downloads/dark-mode-color-audit (1).xlsx'

# Build the set of "official design system" token names by deriving --lt-* canonicals
# from the design palette in the audit xlsx.
def _design_canonical(name):
    parts = name.split('/')
    if parts[0] == 'color': parts = parts[1:]
    return '--lt-' + '-'.join(parts)

DESIGN_TOKENS = set()
try:
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    section = None
    for row in wb['FINAL'].iter_rows(values_only=True):
        a, name, light, dark = row[0], row[1], row[2], row[3]
        if a and not name: section = a; continue
        if not name or not light: continue
        if str(name).upper() == 'TOKENS USED IN DESIGN SYSTEM': continue
        nm = str(name).strip()
        # Targeted rename: design team listed 2 rows under ICON section but
        # named "color/border/X". They were meant to be "color/icon/X".
        if section == 'ICON' and nm.startswith('color/border/'):
            nm = 'color/icon/' + nm.split('/', 2)[2]
        DESIGN_TOKENS.add(_design_canonical(nm))
except Exception as e:
    print(f"warning: could not load design palette: {e}")

# 1. Parse tokens.css → tokens{name: {light, dark}} + utility class map
tokens = {}
CLASS_TO_TOKEN = {}
scheme = None
current_class = None
with open(TOKENS_CSS) as fh:
    for line in fh:
        if line.startswith(':root,'): scheme = 'light'
        elif '[data-color-mode="dark"]' in line: scheme = 'dark'
        elif re.match(r'^\}', line): scheme = None; current_class = None
        if not scheme:
            m = re.match(r'^\.([\w-]+)\s*\{', line)
            if m: current_class = m.group(1)
            if current_class:
                vm = re.search(r'var\((--lt-[a-zA-Z0-9-]+)\)', line)
                if vm: CLASS_TO_TOKEN[current_class] = vm.group(1)
            if re.match(r'^\}', line): current_class = None
            continue
        m = re.match(r'\s*(--lt-[a-zA-Z0-9-]+)\s*:\s*([^;]+);', line)
        if m: tokens.setdefault(m.group(1), {})[scheme] = m.group(2).strip()

def product_of(f):
    if 'tokens.css' in f: return 'internal (tokens.css)'
    if '/lt-components/' in f: return 'lt-components'
    if '/kaneai-test-management-client/' in f: return 'kaneai'
    if '/hyperexecute/' in f: return 'hyperexecute'
    if '/mobile-web-client/' in f: return 'mobile-web-client'
    if '/magic-leap-dashboard/' in f: return 'magic-leap-dashboard'
    if '/packages/' in f: return 'packages'
    return 'other'

def property_of(line, pos, name):
    before = line[:pos]
    # 0. Tailwind arbitrary value: `<util>-[...]` e.g. border-t-[color:var(--x)],
    #    bg-[rgb(from var(--x) ...)], divide-[var(--x)]. MUST run before the CSS rule:
    #    a `[color:` inside the bracket would otherwise falsely match the `color:` property.
    tw = re.search(r'([a-z][a-z0-9]*(?:-[a-z0-9]+)*)-\[[^\]]*$', before)
    if tw:
        keys = set(tw.group(1).split('-'))
        if keys & {'bg', 'from', 'via', 'to'}: return 'bg'
        if keys & {'border', 'divide', 'ring', 'outline'}: return 'border'
        if 'fill' in keys: return 'fill'
        if 'stroke' in keys: return 'stroke'
        if 'shadow' in keys: return 'shadow'
        if keys & {'text', 'caret', 'decoration', 'placeholder', 'accent'}: return 'text'
        # unknown utility — skip CSS/JSX checks (avoid `[color:` trap), use name default
    else:
        # 1. CSS property:  prop: value
        if re.search(r'\b(color|background-color|background|border-color|border-(?:top|right|bottom|left)(?:-color)?|border|outline|box-shadow|fill|stroke)\s*:\s*[^;]*$', before, re.I):
            m = re.search(r'\b(color|background[a-z-]*|border[a-z-]*|outline|box-shadow|fill|stroke)\s*:\s*[^;]*$', before, re.I)
            if m:
                p = m.group(1).lower()
                if p == 'color': return 'text'
                if 'background' in p: return 'bg'
                if 'border' in p or 'outline' in p: return 'border'
                if 'shadow' in p: return 'shadow'
                if p == 'fill': return 'fill'
                if p == 'stroke': return 'stroke'
        # 2. JSX inline-style / attribute
        m = re.search(r'\b(color|backgroundColor|background|borderColor|border[A-Z][a-z]*|outlineColor|boxShadow|fill|stroke|iconColor|tintColor|placeholderColor|hoverColor|fillColor|strokeColor|bgColor|textColor)\s*[:=]\s*[\'"`{][^\'"`}]*$', before)
        if m:
            p = m.group(1).lower()
            if 'fill' in p: return 'fill'
            if 'stroke' in p: return 'stroke'
            if 'shadow' in p: return 'shadow'
            if 'border' in p or 'outline' in p: return 'border'
            if 'background' in p or p == 'bg' or p == 'bgcolor': return 'bg'
            return 'text'
    # 3. name-based default
    if name.startswith('--lt-text-'): return 'text'
    if name.startswith('--lt-bg-'): return 'bg'
    if name.startswith('--lt-border-'): return 'border'
    if name.startswith('--lt-shadow-'): return 'shadow'
    return 'other'

# 1b. Build utility-class -> token maps from each app's tailwind.config.js
#     (after the migration, tokens are consumed via Tailwind utilities, not just var())
import subprocess, json as _json
APP_CONFIGS = {
    'kaneai': (f'{WP}/apps/kaneai-test-management-client', ''),
    'hyperexecute': (f'{WP}/apps/hyperexecute', 'ltw-'),
}
PREFIX_FOR_KEY = {
    'textColor': ['text'], 'backgroundColor': ['bg'],
    'borderColor': ['border', 'border-t', 'border-r', 'border-b', 'border-l', 'border-x', 'border-y'],
    'gradientColorStops': ['from', 'via', 'to'], 'outlineColor': ['outline'],
    'textDecorationColor': ['decoration'], 'divideColor': ['divide'], 'ringColor': ['ring'],
    'fill': ['fill'], 'stroke': ['stroke'], 'caretColor': ['caret'],
    'accentColor': ['accent'], 'placeholderColor': ['placeholder'],
}
GENERAL_PREFIXES = ['text', 'bg', 'border', 'fill', 'stroke', 'from', 'via', 'to', 'outline', 'decoration', 'divide', 'ring', 'caret', 'accent', 'placeholder']
APP_DS = {}      # product -> {(prefix, name): token}
APP_PREFIX = {}  # product -> tailwind prefix
def _flatten(v):
    if isinstance(v, str): return v
    if isinstance(v, dict): return v.get('DEFAULT')
    return None
for _prod, (_cfgdir, _pfx) in APP_CONFIGS.items():
    APP_PREFIX[_prod] = _pfx
    dsmap = {}
    try:
        _out = subprocess.run(['node', '-e',
            "const rc=require('tailwindcss/resolveConfig');const t=rc(require('./tailwind.config.js')).theme;"
            "const ks=['textColor','backgroundColor','borderColor','gradientColorStops','outlineColor','textDecorationColor','divideColor','ringColor','fill','stroke','caretColor','accentColor','placeholderColor','colors'];"
            "const o={};for(const k of ks)o[k]=t[k]||{};console.log(JSON.stringify(o))"],
            capture_output=True, text=True, cwd=_cfgdir).stdout
        _theme = _json.loads(_out or '{}')
    except Exception:
        _theme = {}
    for _key, _m in _theme.items():
        _prefixes = PREFIX_FOR_KEY.get(_key, GENERAL_PREFIXES if _key == 'colors' else [])
        for _name, _val in (_m or {}).items():
            _sval = _flatten(_val)
            if not _sval: continue
            _vm = re.search(r'var\((--lt-[a-zA-Z0-9-]+)\)', _sval)
            if not _vm: continue
            for _pre in _prefixes:
                dsmap[(_pre, _name)] = _vm.group(1)
    APP_DS[_prod] = dsmap
    # plugin lt-* classes (addUtilities) -> CLASS_TO_TOKEN (respectPrefix:false → literal names)
    try:
        _cfgsrc = open(f'{_cfgdir}/tailwind.config.js').read()
    except Exception:
        _cfgsrc = ''
    for _m in re.finditer(r"'\.([a-zA-Z0-9-]+)(?: > \* \+ \*)?':\s*\{\s*'[a-z-]+':\s*'var\((--lt-[a-zA-Z0-9-]+)\)'", _cfgsrc):
        CLASS_TO_TOKEN[_m.group(1)] = _m.group(2)

_DS_PREFIX_ALT = 'border-t|border-r|border-b|border-l|border-x|border-y|text|bg|border|from|via|to|outline|decoration|divide|ring|fill|stroke|caret|accent|placeholder'

# 2. Scan source files for var(--X) and class usage
USAGE = collections.defaultdict(lambda: {'total': 0, 'products': collections.Counter(), 'props': collections.Counter()})
sources = []
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dirpath, dirnames, files in os.walk(root):
        if any(p in dirpath for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dirnames[:] = []; continue
        for fn in files:
            if fn.endswith(('.tsx','.ts','.jsx','.js','.css','.scss','.module.css')):
                sources.append(os.path.join(dirpath, fn))

for path in sources:
    try:
        with open(path) as f: content = f.read()
    except: continue
    is_tokens_css = (path == TOKENS_CSS)
    for line_no, line in enumerate(content.split('\n'), 1):
        for m in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', line):
            name = m.group(1)
            prop = property_of(line, m.end(), name)
            prod = product_of(path)
            USAGE[name]['total'] += 1
            USAGE[name]['products'][prod] += 1
            USAGE[name]['props'][prop] += 1
        if is_tokens_css: continue
        for m in re.finditer(r'\b(lt-[a-zA-Z0-9-]+)\b', line):
            cls = m.group(1)
            if cls not in CLASS_TO_TOKEN: continue
            tk = CLASS_TO_TOKEN[cls]
            before = line[:m.start()]
            if before.endswith('--') or before.endswith('var('): continue
            USAGE[tk]['total'] += 1
            USAGE[tk]['products'][product_of(path)] += 1
            USAGE[tk]['props']['class'] += 1
        # DS Tailwind utilities (bg-base, text-info, bg-ds-primary, ltw-..., incl /opacity)
        _prod = product_of(path)
        _dsmap = APP_DS.get(_prod)
        if _dsmap:
            _pfx = APP_PREFIX.get(_prod, '')
            for m in re.finditer(r'(?<![-a-zA-Z])' + re.escape(_pfx) + r'(' + _DS_PREFIX_ALT + r')-([a-z0-9-]+?)(?:/[0-9]+)?(?![a-z0-9-])', line):
                tk = _dsmap.get((m.group(1), m.group(2)))
                if not tk: continue
                USAGE[tk]['total'] += 1
                USAGE[tk]['products'][_prod] += 1
                USAGE[tk]['props']['tw-class'] += 1

# 3. Render
import datetime
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
sorted_tokens = sorted(tokens.keys(), key=lambda n: (-(USAGE[n]['total']), n))
TOTAL = len(sorted_tokens)
TOTAL_REFS = sum(USAGE[n]['total'] for n in sorted_tokens)
DESIGN_COUNT = sum(1 for n in sorted_tokens if n in DESIGN_TOKENS)

PRODS = ['lt-components', 'kaneai', 'hyperexecute', 'mobile-web-client', 'magic-leap-dashboard', 'packages', 'internal (tokens.css)']

html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>LambdaTest Design Token Sheet</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 16px 24px; font-size: 13px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .meta {{ color: #666; margin-bottom: 16px; }}
  .stats {{ display: flex; gap: 12px; align-items: center; margin: 12px 0 16px; flex-wrap: wrap; }}
  .stat-pill {{ display: inline-flex; align-items: baseline; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 12px; color: #666; }}
  .stat-pill.total {{ background: #ddf4ff; color: #054078; border: 1px solid #b6e3ff; }}
  .stat-pill.filtered {{ background: #fff8c5; color: #693e00; border: 1px solid #f1d878; }}
  .stat-pill .num {{ font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .stat-pill .num-small {{ font-size: 11px; opacity: 0.7; }}
  .stat-pill.hidden {{ display: none; }}
  .controls {{ margin-bottom: 12px; }}
  .controls input {{ padding: 6px 10px; font-size: 13px; width: 280px; }}
  .filter-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }}
  .filter-label {{ font-size: 11px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.5px; min-width: 60px; }}
  .design-badge {{ display: inline-block; font-size: 9px; font-weight: 700; padding: 1px 6px; border-radius: 10px; background: linear-gradient(135deg, #0969da, #054078); color: white; margin-left: 6px; vertical-align: middle; letter-spacing: 0.3px; text-transform: uppercase; }}
  tr.design-token {{ background: #f5fbff; }}
  tr.design-token:hover {{ background: #ebf6ff; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #f6f8fa; text-align: left; padding: 8px 10px; border-bottom: 2px solid #d0d7de; cursor: pointer; user-select: none; font-weight: 600; position: sticky; top: 0; }}
  th:hover {{ background: #eaeef2; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #eef0f3; vertical-align: middle; }}
  .swatch {{ display: inline-block; width: 36px; height: 22px; border-radius: 3px; border: 1px solid rgba(0,0,0,.2); vertical-align: middle; flex-shrink: 0; }}
  .hex-cell {{ display: inline-flex; align-items: center; gap: 8px; }}
  .name {{ font-family: ui-monospace, Menlo, monospace; font-size: 12px; }}
  .hex {{ font-family: ui-monospace, monospace; font-size: 11px; color: #555; }}
  .count {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .props span {{ display: inline-block; margin-right: 6px; padding: 1px 6px; border-radius: 3px; font-size: 10px; background: #eaeef2; color: #333; }}
  .props .text {{ background: #ddf4ff; }}
  .props .bg {{ background: #dafbe1; }}
  .props .border {{ background: #fff8c5; }}
  .props .shadow {{ background: #f6e7ff; }}
  .props .fill, .props .stroke {{ background: #ffe8cc; color: #663300; }}
  .props .class {{ background: #e7e2fd; color: #3a30a0; }}
  .props .other {{ background: #f0f0f0; color: #666; font-style: italic; }}
  .products span {{ font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-right: 4px; background: #f0f0f0; }}
  .row-unused {{ opacity: 0.5; }}
  .filter-buttons button {{ margin-right: 4px; padding: 4px 10px; border: 1px solid #d0d7de; background: white; border-radius: 4px; cursor: pointer; font-size: 12px; }}
  .filter-buttons button.active {{ background: #0969da; color: white; border-color: #0969da; }}
  .nav-link {{ color: #0969da; text-decoration: none; font-size: 12px; margin-left: 8px; }}
</style>
</head><body>
<h1 style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
  LambdaTest Design Token Sheet
  <a href="mapping.html" style="font-size:12px; font-weight:600; padding:6px 14px; border-radius:6px; background:linear-gradient(135deg,#0969da,#054078); color:white; text-decoration:none; letter-spacing:0.3px;">Migration roadmap &amp; mapping →</a>
</h1>
<div class="meta">Generated {now} &middot; <strong>Post-Phase-1 migration</strong> &middot; light + dark scheme &middot; usage across lt-components + lt-web-platform</div>
<div class="stats">
  <span class="stat-pill total"><span class="num" id="total-count">{TOTAL}</span><span>total tokens</span></span>
  <span class="stat-pill total" style="background:#f5fbff;color:#054078;border:1px solid #b6e3ff"><span class="num">{DESIGN_COUNT}</span><span>★ official design tokens</span></span>
  <span class="stat-pill total" style="background:#dafbe1;color:#1a7f37"><span class="num">{TOTAL_REFS:,}</span><span>total references</span></span>
</div>
<div class="controls">
  <input type="text" id="filter" placeholder="Filter tokens (name, hex, product, property...)">
</div>
<div class="filter-row filter-buttons" data-group="prop">
  <span class="filter-label">Property</span>
  <button data-filter="all" class="active">All</button>
  <button data-filter="text">Text</button>
  <button data-filter="bg">Background</button>
  <button data-filter="border">Border</button>
  <button data-filter="shadow">Shadow</button>
  <button data-filter="unused">Unused only</button>
</div>
<div class="filter-row filter-buttons" data-group="source">
  <span class="filter-label">Source</span>
  <button data-source="all" class="active">All</button>
  <button data-source="design">★ Official design system</button>
  <button data-source="non-design">Legacy / orphan</button>
</div>
<div class="filter-row filter-buttons" data-group="ctype">
  <span class="filter-label">Token type</span>
  <button data-ctype="all" class="active">All</button>
  <button data-ctype="c">--lt-c-* (value-encoded)</button>
  <button data-ctype="named">Named (semantic)</button>
</div>
<div class="filter-row filter-buttons" data-group="product">
  <span class="filter-label">Product</span>
  <button data-product="all" class="active">All</button>
  <button data-product="lt-components">lt-components</button>
  <button data-product="kaneai">kaneai</button>
  <button data-product="hyperexecute">hyperexecute</button>
  <button data-product="mobile-web-client">mobile-web-client</button>
  <button data-product="magic-leap-dashboard">magic-leap-dashboard</button>
  <button data-product="packages">packages</button>
  <button data-product="internal">internal (tokens.css)</button>
</div>
<div id="filter-result-stats" style="display:none;align-items:center;gap:10px;margin:6px 0 14px;padding:10px 14px;background:#fff8c5;border:1px solid #f1d878;border-radius:8px;flex-wrap:wrap">
  <span style="font-size:11px;font-weight:700;color:#693e00;text-transform:uppercase;letter-spacing:0.5px">Filtered results</span>
  <span class="stat-pill" style="background:#fff;border:1px solid #d0d7de"><span class="num" id="filtered-count">--</span><span>tokens</span><span class="num-small" id="filtered-pct"></span></span>
  <span class="stat-pill" style="background:#fff;border:1px solid #d0d7de"><span class="num" id="filtered-refs">--</span><span>uses</span></span>
</div>
<table id="tbl">
<thead><tr>
  <th data-sort="name">Token name</th>
  <th data-sort="light">Light</th>
  <th data-sort="dark">Dark</th>
  <th data-sort="count">Uses</th>
  <th data-sort="props">Used as</th>
  <th data-sort="products">Products</th>
</tr></thead><tbody>
"""

for name in sorted_tokens:
    light = tokens[name].get('light', '')
    dark = tokens[name].get('dark', light)
    u = USAGE[name]
    count = u['total']
    sw_light = f"<span class=swatch style='background:{light}'></span>" if light else ''
    sw_dark = f"<span class=swatch style='background:{dark}'></span>" if dark else ''
    prop_chips = ''
    for p, n in sorted(u['props'].items(), key=lambda x: -x[1]):
        prop_chips += f"<span class='{p}'>{p}:{n}</span>"
    if not prop_chips: prop_chips = '<span style="color:#999">—</span>'
    prod_chips = ''
    for p, n in sorted(u['products'].items(), key=lambda x: -x[1]):
        prod_chips += f"<span>{p} ({n})</span>"
    if not prod_chips: prod_chips = '<span style="color:#999">unused</span>'
    products_data = '|'.join(u['products'].keys()).replace('internal (tokens.css)', 'internal')
    primary_prop = u['props'].most_common(1)[0][0] if u['props'] else ''
    is_design = name in DESIGN_TOKENS
    row_classes = []
    if count == 0: row_classes.append('row-unused')
    if is_design: row_classes.append('design-token')
    row_cls = ' '.join(row_classes)
    source = 'design' if is_design else 'non-design'
    badge = ' <span class="design-badge" title="Official design system token">★ Design</span>' if is_design else ''
    html += f"""<tr class="{row_cls}" data-name="{name}" data-prop="{primary_prop}" data-count="{count}" data-products="{products_data}" data-source="{source}">
<td><div class=name>{name}{badge}</div></td>
<td><div class='hex-cell'>{sw_light}<span class=hex>{light}</span></div></td>
<td><div class='hex-cell'>{sw_dark}<span class=hex>{dark}</span></div></td>
<td class=count>{count}</td>
<td class=props>{prop_chips}</td>
<td class=products>{prod_chips}</td></tr>
"""

html += """</tbody></table>
<script>
const rows = document.querySelectorAll('#tbl tbody tr');
const state = { q: '', prop: 'all', product: 'all', source: 'all', ctype: 'all' };
const filterResultStats = document.getElementById('filter-result-stats');
const filteredCountEl = document.getElementById('filtered-count');
const filteredPctEl = document.getElementById('filtered-pct');
const filteredRefsEl = document.getElementById('filtered-refs');

function applyFilters() {
  let visible = 0;
  let visibleRefs = 0;
  rows.forEach(r => {
    let show = true;
    if (state.q && !r.textContent.toLowerCase().includes(state.q)) show = false;
    else if (state.prop !== 'all') {
      if (state.prop === 'unused') { if (r.dataset.count !== '0') show = false; }
      else if (r.dataset.prop !== state.prop) show = false;
    }
    if (show && state.product !== 'all') {
      const products = (r.dataset.products || '').split('|');
      if (!products.includes(state.product)) show = false;
    }
    if (show && state.source !== 'all') {
      if (r.dataset.source !== state.source) show = false;
    }
    if (show && state.ctype !== 'all') {
      const isC = r.dataset.name.startsWith('--lt-c-');
      if (state.ctype === 'c' && !isC) show = false;
      if (state.ctype === 'named' && isC) show = false;
    }
    r.style.display = show ? '' : 'none';
    if (show) { visible++; visibleRefs += parseInt(r.dataset.count || '0', 10); }
  });
  const isFiltered = state.q || state.prop !== 'all' || state.product !== 'all' || state.source !== 'all' || state.ctype !== 'all';
  if (isFiltered) {
    filterResultStats.style.display = 'flex';
    filteredCountEl.textContent = visible.toLocaleString();
    const pct = rows.length > 0 ? Math.round((visible / rows.length) * 100) : 0;
    filteredPctEl.textContent = `(${pct}% of total)`;
    filteredRefsEl.textContent = visibleRefs.toLocaleString();
  } else { filterResultStats.style.display = 'none'; }
}

document.getElementById('filter').addEventListener('input', e => { state.q = e.target.value.toLowerCase(); applyFilters(); });
document.querySelectorAll('.filter-buttons[data-group="prop"] button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.filter-buttons[data-group="prop"] button').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); state.prop = b.dataset.filter; applyFilters();
  });
});
document.querySelectorAll('.filter-buttons[data-group="product"] button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.filter-buttons[data-group="product"] button').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); state.product = b.dataset.product; applyFilters();
  });
});
document.querySelectorAll('.filter-buttons[data-group="source"] button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.filter-buttons[data-group="source"] button').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); state.source = b.dataset.source; applyFilters();
  });
});
document.querySelectorAll('.filter-buttons[data-group="ctype"] button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.filter-buttons[data-group="ctype"] button').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); state.ctype = b.dataset.ctype; applyFilters();
  });
});
document.querySelectorAll('th[data-sort]').forEach(th => {
  let asc = false;
  th.addEventListener('click', () => {
    asc = !asc;
    const sortKey = th.dataset.sort;
    const tbody = document.querySelector('#tbl tbody');
    const sorted = [...rows].sort((a, b) => {
      let av, bv;
      if (sortKey === 'count') { av = +a.dataset.count; bv = +b.dataset.count; }
      else if (sortKey === 'name') { av = a.dataset.name; bv = b.dataset.name; }
      else if (sortKey === 'props') { av = a.dataset.prop; bv = b.dataset.prop; }
      else if (sortKey === 'light') { av = a.cells[1].textContent; bv = b.cells[1].textContent; }
      else if (sortKey === 'dark') { av = a.cells[2].textContent; bv = b.cells[2].textContent; }
      else { av = a.cells[5].textContent; bv = b.cells[5].textContent; }
      return asc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });
    sorted.forEach(r => tbody.appendChild(r));
  });
});
</script></body></html>"""

with open('/tmp/token_sheet.html', 'w') as f: f.write(html)
import shutil
shutil.copy('/tmp/token_sheet.html', '/Users/ravichaudhary/Desktop/LambdaTest/dark-mode-reports/token_sheet.html')
print(f"Total tokens: {TOTAL}")
print(f"Total references: {TOTAL_REFS:,}")
