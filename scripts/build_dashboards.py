"""
Rebuild both dashboards (token_sheet + mapping report) from current state.
Self-contained — doesn't depend on prior /tmp scripts.
"""
import openpyxl, re, os, math, collections, json

TOKENS_CSS = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components/src/styles/tokens.css'
XLSX = '/Users/ravichaudhary/Downloads/dark-mode-color-audit (1).xlsx'
WP = '/Users/ravichaudhary/Desktop/LambdaTest/lt-web-platform-worktrees/feat-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components'
REPORTS = '/Users/ravichaudhary/Desktop/LambdaTest/dark-mode-reports'
DELTA = 5

def parse_hex(s):
    if not s: return None
    s = s.strip().lower()
    m = re.match(r'^#([0-9a-f]{6,8})$', s)
    if m: h=m.group(1); return (int(h[0:2],16),int(h[2:4],16),int(h[4:6],16))
    # 3-char hex shorthand: #abc → #aabbcc
    m = re.match(r'^#([0-9a-f]{3})$', s)
    if m:
        h = m.group(1)
        return (int(h[0]*2,16), int(h[1]*2,16), int(h[2]*2,16))
    m = re.match(r'rgb\((\d+)\s*,?\s+(\d+)\s*,?\s+(\d+)', s)
    if m: return (int(m.group(1)),int(m.group(2)),int(m.group(3)))
    return None

def is_clean_hex(s):
    s = (s or '').strip().lower()
    return bool(re.match(r'^#[0-9a-f]{3,8}$', s))

def rgb_dist(a,b): return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))

# 1. Design palette
wb = openpyxl.load_workbook(XLSX, data_only=True)
ws = wb['FINAL']
design=[]; section=None
for row in ws.iter_rows(values_only=True):
    a,name,light,dark = row[0],row[1],row[2],row[3]
    if a and not name: section=a; continue
    if name and light:
        if str(name).upper() == 'TOKENS USED IN DESIGN SYSTEM': continue
        nm = str(name).strip()
        # Targeted fix: design team has 2 rows listed under ICON section but named
        # `color/border/secondary*`. Those specific rows should be `color/icon/*`.
        # ONLY apply this targeted fix — other segments (overlay/, component/) are valid.
        if section == 'ICON' and nm.startswith('color/border/'):
            nm = 'color/icon/' + nm.split('/', 2)[2]
        design.append({'design':nm,'section':section,'light':str(light).strip().lower(),
                       'dark':str(dark).strip().lower() if dark else '','rgb':parse_hex(str(light))})

# 2. Current tokens
tokens={}; scheme=None
with open(TOKENS_CSS) as fh:
    for line in fh:
        if line.startswith(':root,'): scheme='light'
        elif '[data-color-mode="dark"]' in line: scheme='dark'
        elif line.startswith('}'): scheme=None
        if not scheme: continue
        m = re.match(r'\s*(--lt-[a-zA-Z0-9-]+)\s*:\s*([^;]+);', line)
        if m: tokens.setdefault(m.group(1),{})[scheme]=m.group(2).strip().lower()

# 3. Walk sources, count usages with per-property breakdown
def property_of(line, pos, name):
    before = line[:pos]
    # CSS property: value
    if re.search(r'(color|background-color|background|border-color|border-(?:top|right|bottom|left)(?:-color)?|border|outline|box-shadow|fill|stroke)\s*:\s*[^;]*$', before, re.I):
        m = re.search(r'(color|background[a-z-]*|border[a-z-]*|outline|box-shadow|fill|stroke)\s*:\s*[^;]*$', before, re.I)
        if m:
            p = m.group(1).lower()
            if p == 'color': return 'text'
            if 'background' in p: return 'bg'
            if 'border' in p or 'outline' in p: return 'border'
            if 'shadow' in p: return 'shadow'
            if p == 'fill': return 'fill'
            if p == 'stroke': return 'stroke'
    # JSX inline-style or attribute — match the CLOSEST `prop:` or `prop=` to var()
    # (permissive — allows ternaries between prop and the var())
    last_match = None
    for mm in re.finditer(r'\b(color|backgroundColor|background|borderColor|border[A-Z][a-z]*|outlineColor|boxShadow|fill|stroke|iconColor|tintColor|placeholderColor)\s*[:=]', before):
        last_match = mm
    if last_match:
        p = last_match.group(1).lower()
        if 'fill' in p: return 'fill'
        if 'stroke' in p: return 'stroke'
        if 'shadow' in p: return 'shadow'
        if 'border' in p or 'outline' in p: return 'border'
        if 'background' in p or p == 'bg': return 'bg'
        return 'text'
    # Tailwind bg-[color:var(...)]
    m = re.search(r'\b(bg|text|border|fill|stroke|shadow)-\[color:[^\]]*$', before)
    if m:
        p = m.group(1)
        if p == 'bg': return 'bg'
        if p == 'text': return 'text'
        if p in ('border','fill','stroke','shadow'): return p
    # No name-based fallback — token namespace ≠ usage context. A token named
    # --lt-border-* can be used as bg/shadow/etc.; classifying unclassifiable hits
    # by the token's name over-counts the dominant prop and hides cross-context use.
    return 'other'

# Build utility-class -> token maps from each app's tailwind.config.js so the
# mapping report counts class-based usage (lt-bg-base, bg-base, bg-ds-primary, ...) too.
import subprocess, json as _json
_APP_CONFIGS = {'kaneai': (f'{WP}/apps/kaneai-test-management-client', ''), 'hyperexecute': (f'{WP}/apps/hyperexecute', 'ltw-')}
_PREFIX_FOR_KEY = {'textColor': ['text'], 'backgroundColor': ['bg'],
    'borderColor': ['border', 'border-t', 'border-r', 'border-b', 'border-l', 'border-x', 'border-y'],
    'gradientColorStops': ['from', 'via', 'to'], 'outlineColor': ['outline'], 'textDecorationColor': ['decoration'],
    'divideColor': ['divide'], 'ringColor': ['ring'], 'fill': ['fill'], 'stroke': ['stroke'],
    'caretColor': ['caret'], 'accentColor': ['accent'], 'placeholderColor': ['placeholder']}
_GENERAL_PREFIXES = ['text', 'bg', 'border', 'fill', 'stroke', 'from', 'via', 'to', 'outline', 'decoration', 'divide', 'ring', 'caret', 'accent', 'placeholder']
_CLASS_TO_TOKEN = {}
_APP_DS = {}; _APP_PREFIX = {}
def _flat(v):
    if isinstance(v, str): return v
    if isinstance(v, dict): return v.get('DEFAULT')
    return None
for _prod, (_cd, _pf) in _APP_CONFIGS.items():
    _APP_PREFIX[_prod] = _pf; _dm = {}
    try:
        _o = subprocess.run(['node', '-e',
            "const rc=require('tailwindcss/resolveConfig');const t=rc(require('./tailwind.config.js')).theme;"
            "const ks=['textColor','backgroundColor','borderColor','gradientColorStops','outlineColor','textDecorationColor','divideColor','ringColor','fill','stroke','caretColor','accentColor','placeholderColor','colors'];"
            "const o={};for(const k of ks)o[k]=t[k]||{};console.log(JSON.stringify(o))"],
            capture_output=True, text=True, cwd=_cd).stdout
        _th = _json.loads(_o or '{}')
    except Exception:
        _th = {}
    for _k, _m in _th.items():
        _prefs = _PREFIX_FOR_KEY.get(_k, _GENERAL_PREFIXES if _k == 'colors' else [])
        for _n, _v in (_m or {}).items():
            _sv = _flat(_v)
            if not _sv: continue
            _vm = re.search(r'var\((--lt-[a-zA-Z0-9-]+)\)', _sv)
            if not _vm: continue
            for _p in _prefs: _dm[(_p, _n)] = _vm.group(1)
    _APP_DS[_prod] = _dm
    try: _cs = open(f'{_cd}/tailwind.config.js').read()
    except Exception: _cs = ''
    for _m in re.finditer(r"'\.([a-zA-Z0-9-]+)(?: > \* \+ \*)?':\s*\{\s*'[a-z-]+':\s*'var\((--lt-[a-zA-Z0-9-]+)\)'", _cs):
        _CLASS_TO_TOKEN[_m.group(1)] = _m.group(2)
_DS_ALT = 'border-t|border-r|border-b|border-l|border-x|border-y|text|bg|border|from|via|to|outline|decoration|divide|ring|fill|stroke|caret|accent|placeholder'
def _app_of(path):
    if '/kaneai-test-management-client/' in path: return 'kaneai'
    if '/hyperexecute/' in path: return 'hyperexecute'
    return None
# What property does a Tailwind utility actually set? (categorize usage text/bg/border/… not "class")
_PREFIX_PROP = {
    'text': 'text', 'bg': 'bg', 'border': 'border', 'border-t': 'border', 'border-r': 'border',
    'border-b': 'border', 'border-l': 'border', 'border-x': 'border', 'border-y': 'border',
    'from': 'bg', 'via': 'bg', 'to': 'bg', 'outline': 'border', 'decoration': 'text',
    'divide': 'border', 'ring': 'border', 'fill': 'fill', 'stroke': 'stroke',
    'caret': 'text', 'accent': 'text', 'placeholder': 'text',
}
def _lt_prop(cls):
    if cls.startswith('lt-bg-'): return 'bg'
    if cls.startswith('lt-text-'): return 'text'
    if cls.startswith('lt-border-'): return 'border'
    if cls.startswith('lt-divide-'): return 'border'
    if cls.startswith('lt-fill-'): return 'fill'
    if cls.startswith('lt-stroke-'): return 'stroke'
    return 'other'

usage = collections.Counter()
prop_breakdown = collections.defaultdict(collections.Counter)
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dirpath, dirnames, files in os.walk(root):
        if any(p in dirpath for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dirnames[:] = []; continue
        for fn in files:
            if not fn.endswith(('.tsx','.ts','.jsx','.js','.css','.scss','.module.css')): continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path) as f: content = f.read()
            except: continue
            # Skip tokens.css itself
            if path == TOKENS_CSS: continue
            for m in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', content):
                name = m.group(1)
                # Get line context for property detection
                line_start = content.rfind('\n', 0, m.start()) + 1
                line_end = content.find('\n', m.end())
                if line_end < 0: line_end = len(content)
                line = content[line_start:line_end]
                pos_in_line = m.end() - line_start
                p = property_of(line, pos_in_line, name)
                usage[name] += 1
                prop_breakdown[name][p] += 1
            # lt-* plugin classes + DS Tailwind utilities -> usage (post-migration consumption)
            for m in re.finditer(r'(?<![-a-zA-Z])(lt-[a-zA-Z0-9-]+)(?![a-z0-9-])', content):
                _cls = m.group(1)
                _tk = _CLASS_TO_TOKEN.get(_cls)
                if _tk: usage[_tk] += 1; prop_breakdown[_tk][_lt_prop(_cls)] += 1
            _app = _app_of(path)
            if _app and _app in _APP_DS:
                _pf = _APP_PREFIX[_app]; _dm = _APP_DS[_app]
                for m in re.finditer(r'(?<![-a-zA-Z])' + re.escape(_pf) + r'(' + _DS_ALT + r')-([a-z0-9-]+?)(?:/[0-9]+)?(?![a-z0-9-])', content):
                    _tk = _dm.get((m.group(1), m.group(2)))
                    if _tk: usage[_tk] += 1; prop_breakdown[_tk][_PREFIX_PROP.get(m.group(1), 'other')] += 1

# 4. Build mapping: per design token, find current tokens within Δ ≤ 5 in matching section
def section_of(name):
    if name.startswith('--lt-text-') or name.endswith('-fg'): return 'TEXT'
    if name.startswith('--lt-bg-') or '-bg-' in name or name.endswith('-bg'): return 'BACKGROUND'
    if name.startswith('--lt-border-') or '-border-' in name: return 'BORDER'
    if name.startswith('--lt-shadow-'): return 'SHADOW'
    if name.startswith('--lt-icon-'): return 'ICON'
    if name.startswith('--lt-component-'): return 'COMPONENT SPECIFIC'
    if '--lt-primer-fg' in name: return 'TEXT'
    if '--lt-primer-canvas' in name: return 'BACKGROUND'
    if '--lt-primer-border' in name: return 'BORDER'
    if name.endswith('-emphasis') or name.endswith('-muted') or name.endswith('-subtle'): return 'BACKGROUND'
    p = prop_breakdown[name].most_common(1)
    if p:
        primary = p[0][0]
        if primary == 'text': return 'TEXT'
        if primary == 'bg': return 'BACKGROUND'
        if primary == 'border': return 'BORDER'
        if primary == 'shadow': return 'SHADOW'
        if primary in ('fill','stroke'): return 'ICON'
    return None

# Direct exact matches
direct_match = collections.defaultdict(list)
matched = set()
for d in design:
    for tname, tv in tokens.items():
        if tv.get('light','').strip().lower() == d['light']:
            direct_match[d['design']].append((tname, usage.get(tname,0)))
            matched.add(tname)

# Per-orphan recommendation
recommendations = []; unmappable=[]
for tname, tv in tokens.items():
    if tname in matched: continue
    light_str = tv.get('light',''); dark_str = tv.get('dark','')
    rgb = parse_hex(light_str)
    rec = {'name':tname,'light':light_str,'dark':dark_str,'usage':usage.get(tname,0)}
    if rgb is None:
        rec['target']=None; unmappable.append(rec); continue
    sec = section_of(tname)
    pool = [d for d in design if d['rgb'] and (sec is None or d['section']==sec)]
    if not pool: pool = [d for d in design if d['rgb']]
    best, best_d = None, float('inf')
    for d in pool:
        dist = rgb_dist(rgb, d['rgb'])
        if dist < best_d: best, best_d = d, dist
    rec['target'] = best['design'] if best else None
    rec['target_light'] = best['light'] if best else ''
    rec['target_dark'] = best['dark'] if best else ''
    rec['distance'] = round(best_d, 1)
    recommendations.append(rec)

# Group by recommended target
by_target = collections.defaultdict(list)
for rec in recommendations:
    by_target[rec['target']].append(rec)
for k in by_target:
    by_target[k].sort(key=lambda r:-r['usage'])
target_order = []
seen = set()
for d in design:
    if d['design'] in by_target and d['design'] not in seen:
        seen.add(d['design']); target_order.append(d)

# Near-matches covering "missing" design tokens
near_for_design = collections.defaultdict(list)
for rec in recommendations:
    if rec['target'] and rec['distance'] <= DELTA:
        near_for_design[rec['target']].append((rec['name'], rec['distance'], rec['usage']))
for k in near_for_design:
    near_for_design[k].sort(key=lambda x:(x[1],-x[2]))

covered_exact=[]; covered_near=[]; truly_missing=[]
for d in design:
    if direct_match.get(d['design']): covered_exact.append(d)
    elif near_for_design.get(d['design']): covered_near.append(d)
    else: truly_missing.append(d)

# Counts
n_design = len(design)
n_total = len(tokens)
n_recs = len(recommendations)
n_unmappable = len(unmappable)
n_exact = len(covered_exact)
n_near = len(covered_near)
n_missing = len(truly_missing)

# Migration progress stats — fine delta bands
coverage_pct = round(100 * n_exact / n_design) if n_design else 0

# Bands: ≤5, 6-10, 11-20, then steps of 20 up to max (21-40, 41-60, ...), then > max-band
max_delta = max((r['distance'] for r in recommendations), default=0)

def band_for(d):
    if d <= 5: return ('le5', '≤ 5', 0, 5)
    if d <= 10: return ('5_10', '6–10', 5, 10)
    if d <= 20: return ('10_20', '11–20', 10, 20)
    # After 20, step by 20
    band_low = ((int(d - 0.0001) // 20) * 20)
    band_high = band_low + 20
    return (f'{band_low}_{band_high}', f'{band_low+1}–{band_high}', band_low, band_high)

import collections as _c
band_count = _c.Counter()
band_consumers = _c.Counter()
band_label = {}  # key → display label
band_range = {}  # key → (low, high)
for r in recommendations:
    key, label, lo, hi = band_for(r['distance'])
    band_count[key] += 1
    band_consumers[key] += r['usage']
    band_label[key] = label
    band_range[key] = (lo, hi)

# Stable order: ≤5 → 6-10 → 11-20 → 21-40 → 41-60 → ...
def band_sort_key(k):
    return band_range[k][0]
ordered_bands = sorted(band_count.keys(), key=band_sort_key)

# ─────────────────────────────────────────────────────────────────────────────
# Render token mapping HTML
# ─────────────────────────────────────────────────────────────────────────────
def swatch(hex_str): return f"<span class='swatch' style='background:{hex_str}'></span>" if is_clean_hex(hex_str) else ''

# Build band stats HTML
# Color gradient from green (low delta) → yellow → orange → red (high delta)
def band_color(key):
    if key == 'le5': return ('#dafbe1', '#1a7f37')
    if key == '5_10': return ('#d2f4d8', '#1a7f37')
    if key == '10_20': return ('#fff8c5', '#693e00')
    low, _ = band_range.get(key, (0, 0))
    if low < 40: return ('#ffe2c2', '#9a4a00')
    if low < 60: return ('#ffd0a0', '#9a4a00')
    if low < 80: return ('#ffc2a0', '#7a3a00')
    if low < 100: return ('#ffbabb', '#82071e')
    if low < 140: return ('#ffacaf', '#82071e')
    return ('#ffe0e0', '#82071e')

band_stats_pills = ''
for k in ordered_bands:
    bg, fg = band_color(k)
    label = band_label[k]
    band_stats_pills += (
        f'<span class="stat band-pill" style="background:{bg};color:{fg};cursor:pointer;" data-band="{k}" title="Click to filter to Δ {label}">'
        f'<span class="num">{band_count[k]}</span> Δ {label} · {band_consumers[k]:,} uses</span>'
    )
BAND_STATS_HTML = f'<div class="stats" style="margin-top:-8px;flex-wrap:wrap">{band_stats_pills}</div>'

# Filter dropdown options
filter_options = ['<option value="all">All deltas</option>']
for k in ordered_bands:
    lo, hi = band_range[k]
    if k == 'le5':
        filter_options.append(f'<option value="band-{k}">Δ ≤ 5</option>')
    else:
        filter_options.append(f'<option value="band-{k}">Δ {band_label[k]}</option>')
# Also add cumulative options for quick filtering
filter_options.insert(2, '<option value="cum-10">Δ ≤ 10 (cumulative)</option>')
filter_options.insert(3, '<option value="cum-20">Δ ≤ 20 (cumulative)</option>')
filter_options.insert(4, '<option value="cum-50">Δ ≤ 50 (cumulative)</option>')
FILTER_OPTIONS_HTML = '\n'.join('  ' + o for o in filter_options)

mapping_out = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Token Mapping &amp; Recommendations</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 16px 24px; font-size: 13px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ margin: 24px 0 8px; padding-bottom: 4px; border-bottom: 2px solid #d0d7de; font-size: 16px; }}
  h3 {{ margin: 16px 0 6px; font-size: 13px; color: #054078; padding: 6px 10px; background: #ddf4ff; border-radius: 4px; display: flex; align-items: center; gap: 8px; }}
  h3 .group-count {{ font-size: 11px; color: #666; font-weight: normal; margin-left: auto; }}
  .meta {{ color: #666; margin-bottom: 16px; }}
  .stats {{ display: flex; gap: 12px; margin: 12px 0 20px; flex-wrap: wrap; }}
  .stat {{ padding: 8px 14px; border-radius: 8px; font-size: 12px; }}
  .stat .num {{ font-size: 22px; font-weight: 700; display: inline-block; margin-right: 4px; }}
  .stat.total {{ background: #ddf4ff; color: #054078; }}
  .stat.mapped {{ background: #dafbe1; color: #1a7f37; }}
  .stat.orphan {{ background: #fff8c5; color: #693e00; }}
  .stat.unmappable {{ background: #ffebe9; color: #82071e; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; }}
  th {{ background: #f6f8fa; text-align: left; padding: 8px 10px; border-bottom: 2px solid #d0d7de; font-weight: 600; font-size: 12px; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #eef0f3; vertical-align: middle; }}
  .swatch {{ display: inline-block; width: 28px; height: 18px; border-radius: 3px; border: 1px solid rgba(0,0,0,.18); vertical-align: middle; margin-right: 6px; }}
  .hex {{ font-family: ui-monospace, monospace; font-size: 11px; color: #555; }}
  .design-name {{ font-family: ui-monospace, monospace; font-size: 12px; font-weight: 600; color: #054078; }}
  .current-name {{ font-family: ui-monospace, monospace; font-size: 11px; color: #333; }}
  .usage {{ font-size: 10px; color: #666; padding: 1px 6px; background: #f0f0f0; border-radius: 10px; display: inline-block; }}
  .delta {{ font-size: 11px; padding: 1px 6px; border-radius: 3px; font-family: ui-monospace, monospace; }}
  .delta-good {{ background: #dafbe1; color: #1a7f37; }}
  .delta-ok {{ background: #fff8c5; color: #693e00; }}
  .delta-poor {{ background: #ffebe9; color: #82071e; }}
  .controls {{ margin: 12px 0; position: sticky; top: 0; background: white; padding: 8px 0; z-index: 10; border-bottom: 1px solid #eef0f3; }}
  .controls input {{ padding: 6px 10px; font-size: 13px; width: 320px; }}
  .controls select {{ padding: 6px 10px; font-size: 13px; margin-left: 8px; }}
  .arrow {{ color: #888; padding: 0 6px; }}
  .group {{ margin-bottom: 20px; }}
  .nav-tabs {{ display: flex; gap: 4px; margin: 16px 0 8px; border-bottom: 2px solid #d0d7de; }}
  .nav-tabs button {{ padding: 8px 16px; border: none; background: transparent; cursor: pointer; font-size: 13px; font-weight: 600; color: #666; border-bottom: 3px solid transparent; }}
  .nav-tabs button.active {{ color: #054078; border-bottom-color: #0969da; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
  .legend {{ font-size: 11px; color: #666; margin-bottom: 8px; }}
</style>
</head><body>
<h1 style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
  Token Mapping &amp; Migration Recommendations
  <a href="index.html" style="font-size:12px; font-weight:600; padding:6px 14px; border-radius:6px; background:#f6f8fa; color:#054078; text-decoration:none; border:1px solid #d0d7de;">← Back to token sheet</a>
</h1>
<div class="meta">Phase 1 complete — 100% design system coverage in tokens.css. Showing migration roadmap for remaining legacy/orphan tokens.</div>
<div class="stats">
  <span class="stat total"><span class="num">{n_recs}</span> orphans remaining</span>
</div>
{BAND_STATS_HTML}
<div class="legend">
  Color delta: <span class="delta delta-good">≤ 5 near-identical</span>
  <span class="delta delta-ok">6–25 acceptable</span>
  <span class="delta delta-poor">&gt; 25 visible drift</span>
</div>
<div class="nav-tabs">
  <button class="active" data-tab="recommendations">Migration roadmap ({n_recs} orphans)</button>
  <button data-tab="exact">Design system tokens ({n_exact})</button>
  <button data-tab="unmappable">Manual review ({n_unmappable})</button>
</div>
<div class="controls">
  <input type="text" id="filter" placeholder="Filter by token name, hex, or target...">
  <select id="delta-filter">
{FILTER_OPTIONS_HTML}
  </select>
</div>
<div id="tab-recommendations" class="tab-content active">
"""

for d in target_order:
    group = by_target[d['design']]
    total = sum(r['usage'] for r in group)
    mapping_out += f"""<div class="group" data-target="{d['design']}">
<h3>{swatch(d['light'])}<span class='design-name'>{d['design']}</span> {swatch(d['dark'])}<span class='hex'>{d['light']} / {d['dark']}</span>
<span class='group-count'>{len(group)} orphans · {total:,} total usages</span></h3>
<table><thead><tr><th style="width:32%">Current orphan</th><th style="width:14%">Light</th><th style="width:14%">Dark</th><th style="width:8%">Δ</th><th style="width:8%; text-align:right">Uses</th><th>Recommendation</th></tr></thead><tbody>"""
    for rec in group:
        ds = rec['distance']
        # Visual class for the chip color
        if ds <= 5: chip_cls = 'delta-good'
        elif ds <= 20: chip_cls = 'delta-ok'
        else: chip_cls = 'delta-poor'
        band_key, _, _, _ = band_for(ds)
        mapping_out += f"""<tr data-search="{rec['name']} {rec['light']} {d['design']}" data-delta="{chip_cls}" data-band="{band_key}" data-distance="{ds}">
<td><span class='current-name'>{rec['name']}</span></td>
<td>{swatch(rec['light'])}<span class='hex'>{rec['light']}</span></td>
<td>{swatch(rec['dark'])}<span class='hex'>{rec['dark']}</span></td>
<td><span class='delta {chip_cls}'>{ds}</span></td>
<td style='text-align:right'>{rec['usage']:,}</td>
<td><span class='arrow'>→</span><span class='design-name'>{d['design']}</span></td></tr>"""
    mapping_out += "</tbody></table></div>"
mapping_out += "</div>"

# Tab 2: design system catalog — show ALL 97 official tokens grouped by section
mapping_out += '<div id="tab-exact" class="tab-content"><p style="color:#666">The official design system palette as currently present in tokens.css — all 97 tokens. Use this as a reference when picking colors.</p>'

import collections as _c
by_section = _c.OrderedDict()
for d in design:
    by_section.setdefault(d['section'], []).append(d)

for sec_name, sec_tokens in by_section.items():
    mapping_out += f"<h3>{sec_name} ({len(sec_tokens)})</h3>"
    mapping_out += '<table><thead><tr><th style="width:40%">Design Token</th><th>Light</th><th>Dark</th><th>Canonical --lt-* name</th></tr></thead><tbody>'
    for d in sec_tokens:
        parts = d['design'].split('/')
        if parts[0] == 'color': parts = parts[1:]
        canonical = '--lt-' + '-'.join(parts)
        mapping_out += f"""<tr data-search="{d['design']} {canonical}">
<td><span class='design-name'>{d['design']}</span></td>
<td>{swatch(d['light'])}<span class='hex'>{d['light']}</span></td>
<td>{swatch(d['dark'])}<span class='hex'>{d['dark']}</span></td>
<td><span class='current-name'>{canonical}</span></td></tr>"""
    mapping_out += '</tbody></table>'
mapping_out += '</div>'

# Tab 3: unmappable
mapping_out += '<div id="tab-unmappable" class="tab-content"><table><thead><tr><th>Token</th><th>Light</th><th>Dark</th><th style="text-align:right">Uses</th></tr></thead><tbody>'
for rec in sorted(unmappable, key=lambda r:-r['usage']):
    mapping_out += f"""<tr data-search="{rec['name']}"><td><span class='current-name'>{rec['name']}</span></td>
<td><span class='hex'>{rec['light']}</span></td>
<td><span class='hex'>{rec['dark']}</span></td>
<td style='text-align:right'>{rec['usage']:,}</td></tr>"""
mapping_out += '</tbody></table></div>'

# JS
mapping_out += """
<script>
document.querySelectorAll('.nav-tabs button').forEach(b=>{
  b.addEventListener('click',()=>{
    document.querySelectorAll('.nav-tabs button').forEach(x=>x.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    document.getElementById('tab-'+b.dataset.tab).classList.add('active');
  });
});
function passesDelta(r, dq) {
  if (dq === 'all') return true;
  const dist = parseFloat(r.dataset.distance || '0');
  // Cumulative filters: cum-N → ≤ N
  const cumMatch = dq.match(/^cum-(\d+)$/);
  if (cumMatch) return dist <= parseInt(cumMatch[1]);
  // Band-specific filter: band-<key> matches rows whose data-band attribute equals key
  if (dq.startsWith('band-')) {
    const key = dq.slice(5);
    return r.dataset.band === key;
  }
  return true;
}
function applyFilter(){
  const q=document.getElementById('filter').value.toLowerCase();
  const dq=document.getElementById('delta-filter').value;
  document.querySelectorAll('.tab-content tr[data-search]').forEach(r=>{
    const t=(r.dataset.search||'').toLowerCase();
    const hits=!q||t.includes(q);
    const hitsD=passesDelta(r, dq);
    r.style.display=(hits&&hitsD)?'':'none';
  });
  document.querySelectorAll('#tab-recommendations .group').forEach(g=>{
    const v=[...g.querySelectorAll('tbody tr')].some(r=>r.style.display!=='none');
    g.style.display=v?'':'none';
  });
}
document.getElementById('filter').addEventListener('input',applyFilter);
document.getElementById('delta-filter').addEventListener('change',applyFilter);
// Click any band pill to filter to that band (or click again to reset)
document.querySelectorAll('.band-pill').forEach(p=>{
  p.addEventListener('click',()=>{
    const dq=document.getElementById('delta-filter');
    const target='band-'+p.dataset.band;
    if (dq.value===target) { dq.value='all'; } else { dq.value=target; }
    applyFilter();
    p.scrollIntoView({behavior:'smooth',block:'nearest'});
  });
});
</script></body></html>"""

with open('/tmp/token_mapping.html','w') as f: f.write(mapping_out)
import shutil
shutil.copy('/tmp/token_mapping.html', f'{REPORTS}/token_mapping.html')

# Summary
delta_buckets = collections.Counter()
for r in recommendations:
    if r['distance'] <= 5: delta_buckets['≤5'] += 1
    elif r['distance'] <= 25: delta_buckets['6-25'] += 1
    else: delta_buckets['>25'] += 1

print(f"=== Updated mapping report ===")
print(f"Design tokens:    {n_design}")
print(f"  exact matches:  {n_exact}")
print(f"  near-matches:   {n_near}")
print(f"  truly missing:  {n_missing}")
print(f"Current tokens:   {n_total}")
print(f"  orphans:        {n_recs}")
print(f"    Δ ≤ 5:        {delta_buckets['≤5']}")
print(f"    Δ 6-25:       {delta_buckets['6-25']}")
print(f"    Δ > 25:       {delta_buckets['>25']}")
print(f"  non-hex:        {n_unmappable}")
print(f"\nLocal: {REPORTS}/token_mapping.html")
