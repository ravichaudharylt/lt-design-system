"""Generate orphan-replacements.html — audit log for deprecated tokens and their canonical DS replacements.

Source of truth:
  - /Users/ravichaudhary/Desktop/LambdaTest/lt-web-platform-worktrees/feat-dark-mode/OrphanTokens.txt
  - lt-components/src/styles/tokens.css (for L/D hex lookup)
  - dark-mode-color-audit (1).xlsx FINAL sheet (canonical 112-token DS set)
  - worktree apps/+packages/ for usage counts
"""
import re, os, html, collections, openpyxl, json, datetime, sys

WP   = '/Users/ravichaudhary/Desktop/LambdaTest/lt-web-platform-worktrees/feat-dark-mode'
LTC  = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components'
XLSX = '/Users/ravichaudhary/Downloads/dark-mode-color-audit (1).xlsx'
OUT  = '/tmp/lt-design-system/mapped.html'

# canonical DS set
ws = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)['FINAL']
canon = set()
for r in ws.iter_rows(values_only=True):
    v = r[1]
    if isinstance(v, str):
        m = re.fullmatch(r'color/([a-z0-9/-]+)', v.strip())
        if m: canon.add('--lt-' + m.group(1).replace('/', '-'))

# light/dark token map
text = open(f'{LTC}/src/styles/tokens.css').read()
m = re.search(r':root[^{]*\{(.*?)^\}', text, re.S | re.M); light_text = m.group(1)
m = re.search(r'\[data-color-mode="dark"\][^{]*\{(.*?)^\}', text, re.S | re.M); dark_text = m.group(1) if m else ''
LIGHT = {n: v.strip() for n, v in re.findall(r'(--lt-[a-z0-9-]+)\s*:\s*([^;]+);', light_text)}
DARK  = {n: v.strip() for n, v in re.findall(r'(--lt-[a-z0-9-]+)\s*:\s*([^;]+);', dark_text)}

# Mapping table (DS-canonical-only). Reflects OrphanTokens.txt + corrections.
MAPPINGS = {
    # REMOVE — usages become hex literal, token deleted from tokens.css
    '--lt-c-fffafa':   ('REMOVE',  '#fffafa', ''),
    '--lt-c-faebe7':   ('REMOVE',  '#faebe7', ''),
    '--lt-c-f3feff':   ('REMOVE',  '#f3feff', ''),
    '--lt-c-e06c6b':   ('REMOVE',  '#e06c6b', ''),
    '--lt-c-e5e6e9':   ('REMOVE',  '#e5e6e9', ''),
    '--lt-c-dfe0e4':   ('REMOVE',  '#dfe0e4', ''),
    '--lt-c-d0d1d5':   ('REMOVE',  '#d0d1d5', ''),
    '--lt-c-108404':   ('REMOVE',  '#108404', ''),
    '--lt-c-05e7e6':   ('REMOVE',  '#05e7e6', ''),
    # REPLACE — all targets ∈ canonical 112-token DS set
    '--lt-c-e12826':            ('REPLACE', '--lt-text-error',        'red — per context'),
    '--lt-c-353535':            ('REPLACE', '--lt-border-secondary',  ''),
    '--lt-c-1d1a1a':            ('REPLACE', '--lt-text-primary',      ''),
    '--lt-c-ffbeb8':            ('REPLACE', '--lt-bg-error-muted',    'Flash danger (no flash token)'),
    '--lt-c-0249b3':            ('REPLACE', '--lt-text-info',         'blue — per context'),
    '--lt-c-fcf5da':            ('REPLACE', '--lt-bg-warning-muted',  'tag-yellow → warning-muted (hex match)'),
    '--lt-c-fbdada':            ('REPLACE', '--lt-bg-error-muted',    'tag-pink → error-muted (hex match)'),
    '--lt-c-ee6d51':            ('REPLACE', '--lt-bg-brand-primary',  'invisible-btn orange → brand orange'),
    '--lt-c-e2e2ee':            ('REPLACE', '--lt-border-secondary',  ''),
    '--lt-c-e1e9ec':            ('REPLACE', '--lt-border-secondary',  ''),
    '--lt-c-c1c1c1':            ('REPLACE', '--lt-text-secondary',    ''),
    '--lt-c-bfbfbf':            ('REPLACE', '--lt-text-secondary',    'verify'),
    '--lt-c-bae6ff':            ('REPLACE', '--lt-bg-info-muted',     'tag-blueAccent → info-muted'),
    '--lt-c-a10707':            ('REPLACE', '--lt-text-error',        'red — per context'),
    '--lt-c-463c3c':            ('REPLACE', '--lt-text-primary',      ''),
    '--lt-c-3fb950':            ('REPLACE', '--lt-text-success',      'also audit --lt-c-d29922 in LogLevels'),
    '--lt-c-3498db':            ('REPLACE', '--lt-text-info',         'blue — per context'),
    '--lt-c-eb5757':            ('REPLACE', '--lt-text-error',        'confirm w/ Rajat'),
    '--lt-c-252525':            ('REPLACE', '--lt-text-primary',      ''),
    '--lt-c-ff6600':            ('REPLACE', '--lt-text-error',        'severe → error (canonical)'),
    '--lt-c-ff5757':            ('REPLACE', '--lt-text-error',        'severe → error (canonical)'),
    '--lt-c-de2d2d':            ('REPLACE', '--lt-text-error',        'red — per context'),
    '--lt-c-101001':            ('REPLACE', '--lt-text-primary',      ''),
    '--lt-c-e9e9e9':            ('REPLACE', '--lt-border-secondary',  'border-only'),
    '--lt-c-0366d6':            ('REPLACE', '--lt-text-info',         'blue — per context'),
    '--lt-c-488c31':            ('REPLACE', '--lt-text-success',      ''),
    '--lt-c-747474':            ('REPLACE', '--lt-text-muted',        ''),
    '--lt-c-409ff6':            ('REPLACE', '--lt-text-info',         ''),
    '--lt-border-muted':        ('REPLACE', '--lt-border-secondary',  'border-only; leave bg-* as-is'),
    '--lt-text-black':          ('REPLACE', '--lt-text-primary',      'text-only'),
    '--lt-bg-progress':         ('REPLACE', '--lt-border-secondary',  'border-only'),
    '--lt-text-tertiary':       ('REPLACE', '--lt-text-muted',        'text-only'),
    '--lt-bg-active':           ('REPLACE', '--lt-bg-base-muted',     'bg-only'),
    '--lt-text-gray-999':       ('REPLACE', '--lt-text-secondary',    'text-only'),
    '--lt-text-dark-1f':        ('REPLACE', '--lt-text-primary',      'text-only'),
    '--lt-bg-gray-100':         ('REPLACE', '--lt-bg-base-muted',     'bg-only'),
    '--lt-border-eee':          ('REPLACE', '--lt-bg-base-muted',     'bg-only (despite name)'),
    '--lt-bg-eaeaea':           ('REPLACE', '--lt-border-secondary',  'border-only (despite name)'),
    '--lt-text-red-ff6':        ('REPLACE', '--lt-text-error',        'text-only'),
    '--lt-text-gray-576':       ('REPLACE', '--lt-text-secondary',    'text-only'),
    '--lt-primer-accent-muted': ('REPLACE', '--lt-border-info-muted', 'border-only; target has α66'),
    '--lt-border-ccc':          ('REPLACE', '--lt-border-secondary',  'border-only'),
    '--lt-border-e0':           ('REPLACE', '--lt-border-secondary',  'border-only'),
    '--lt-bg-success-btn':      ('REPLACE', '--lt-bg-success',        'bg-only'),
    '--lt-border-e1e':          ('REPLACE', '--lt-border-secondary',  'border-only'),
    '--lt-text-error-red':      ('REPLACE', '--lt-text-error',        'text-only'),
    '--lt-text-gray-9b':        ('REPLACE', '--lt-text-disabled',     'text-only'),
    '--lt-bg-tag':              ('REPLACE', '--lt-bg-base-muted',     'bg-only'),
    '--lt-status-severe-fg':    ('REPLACE', '--lt-text-error',        'text-only'),
    '--lt-text-gray-6a7':       ('REPLACE', '--lt-text-secondary',    'text-only'),
    '--lt-text-light-gray':     ('REPLACE', '--lt-text-secondary',    'text-only'),
    '--lt-primer-danger-muted': ('REPLACE', '--lt-border-error-muted', 'target has α66'),
    '--lt-accent-brand':        ('REPLACE', '--lt-bg-brand-primary',  'bg-only'),
    '--lt-border-dada':         ('REPLACE', '--lt-border-secondary',  'border-only'),
    # PENDING
    '--lt-c-e7f0f9':            ('PENDING', '?',                      'awaiting Komal confirmation'),
}

# verify canonical compliance
for s, (action, target, _) in MAPPINGS.items():
    if action == 'REPLACE' and target not in canon:
        print(f"⚠ canonical violation: {s} → {target}", file=sys.stderr)

# usage counts in worktree
files = []
for root in [f'{WP}/apps', f'{WP}/packages']:
    for dp, dns, fns in os.walk(root):
        if any(p in dp for p in ['/node_modules/', '/build/', '/lib/']): dns[:] = []; continue
        for fn in fns:
            if fn.endswith(('.tsx', '.ts', '.jsx', '.js', '.css', '.scss')):
                files.append(os.path.join(dp, fn))
usage = collections.Counter()
for f in files:
    try: c = open(f).read()
    except: continue
    for m in re.finditer(r'var\((--lt-[a-z0-9-]+)\)', c): usage[m.group(1)] += 1

def hex_only(v):
    """Pull a single hex from a token value (or return the value as-is if not a hex)."""
    if not v: return ''
    m = re.match(r'#[0-9a-fA-F]{3,8}', v.strip())
    return m.group(0) if m else v.strip()

# --- Δ≤5 HISTORICAL MAPPINGS — already-executed NON-canonical → canonical migrations
# from commit 22e01ae4c (lt-web-platform feat/dark-mode worktree):
#   "feat(dark-mode): align consumers with design system canonical tokens"
#   "Phase 1 token migration applied: 6,449 consumer references redirected from legacy
#    --lt-* names to canonical design tokens"
# All source tokens here have since been REMOVED from lt-components/src/styles/tokens.css.
# Source L/D values are looked up from commit 01006cc (last lt-components SHA where every
# legacy source still existed); target L/D from current tokens.css.
HISTORICAL_DELTA_SWAPS = [
    # (source, target, swap_count)  — only NON-canonical → canonical pairs (88 of 90 total)
    ('--lt-text-gray-636',         '--lt-text-secondary',         454),
    ('--lt-text-link',             '--lt-text-info',              432),
    ('--lt-text-on-emphasis',      '--lt-text-inverse',           358),
    ('--lt-status-danger-fg',      '--lt-text-error',             355),
    ('--lt-text-dark-24',          '--lt-text-primary',           330),
    ('--lt-text-subtle',           '--lt-text-muted',             303),
    ('--lt-accent-primary',        '--lt-text-info',              284),
    ('--lt-border-neutral-light',  '--lt-border-secondary',       269),
    ('--lt-bg-hover',              '--lt-bg-base-muted',          257),
    ('--lt-bg-muted',              '--lt-bg-base-muted',          254),
    ('--lt-status-success-fg-alt', '--lt-text-success',           107),
    ('--lt-accent-purple-fg',      '--lt-text-purple',             94),
    ('--lt-status-warning-fg',     '--lt-text-warning',            77),
    ('--lt-shadow-tint-medium',    '--lt-shadow-floating-small-2', 45),
    ('--lt-text-gray-8c9',         '--lt-text-disabled',           45),
    ('--lt-status-danger-fg-alt',  '--lt-text-error',              43),
    ('--lt-status-danger-bg',      '--lt-bg-error-muted',          41),
    ('--lt-accent-primary-muted',  '--lt-bg-info-muted',           39),
    ('--lt-text-gray-656',         '--lt-text-secondary',          36),
    ('--lt-border-accent',         '--lt-border-info',             28),
    ('--lt-bg-f6f7',               '--lt-bg-base-muted',           23),
    ('--lt-orange-bg',             '--lt-bg-brand-secondary',      22),
    ('--lt-btn-success-bg',        '--lt-bg-primary',              22),
    ('--lt-text-orange-bc',        '--lt-text-orange',             18),
    ('--lt-c-ecf0f1',              '--lt-bg-base-disabled',        15),
    ('--lt-status-warning-bg',     '--lt-bg-warning-muted',        14),
    ('--lt-c-a40e26',              '--lt-bg-error-hover',          14),
    ('--lt-status-success-bg',     '--lt-bg-success-muted',        11),
    ('--lt-bg-skeleton',           '--lt-bg-base-pressed',         11),
    ('--lt-c-21262d',              '--lt-bg-base-inverse',         10),
    ('--lt-bg-ebec',               '--lt-bg-base-pressed',          8),
    ('--lt-bg-near-white-alt',     '--lt-bg-base',                  8),
    ('--lt-bg-success-btn-muted2', '--lt-bg-primary-disabled',      7),
    ('--lt-c-e6edf3',              '--lt-bg-base-pressed',          7),
    ('--lt-bg-quaternary',         '--lt-bg-base-muted',            7),
    ('--lt-c-edf0f3',              '--lt-bg-base-disabled',         6),
    ('--lt-accent-purple-muted',   '--lt-bg-purple-muted',          6),
    ('--lt-c-e9eff4',              '--lt-bg-base-disabled',         6),
    ('--lt-status-warning-pale-bg','--lt-bg-orange-muted',          6),
    ('--lt-primer-fg-subtle-dark', '--lt-text-muted',               6),
    ('--lt-bg-f8f8f8',             '--lt-bg-base-muted',            5),
    ('--lt-c-ffeff7',              '--lt-bg-magenta-muted',         5),
    ('--lt-bg-muted-hover',        '--lt-bg-base-disabled',         5),
    ('--lt-text-pink',             '--lt-text-magenta',             5),
    ('--lt-border-danger',         '--lt-border-error',             5),
    ('--lt-bg-f4f5',               '--lt-bg-base-muted',            5),
    ('--lt-c-6c757d',              '--lt-text-muted',               4),
    ('--lt-c-1c8139',              '--lt-text-success',             4),
    ('--lt-bg-chip-selected',      '--lt-bg-base-disabled',         4),
    ('--lt-border-subtle',         '--lt-border-secondary',         4),
    ('--lt-tooltip-bg',            '--lt-bg-base-inverse',          3),
    ('--lt-border-d1d5',           '--lt-border-secondary',         3),
    ('--lt-bg-f8f9fa',             '--lt-bg-base-muted',            3),
    ('--lt-c-fefefe',              '--lt-icon-transparent',         3),
    ('--lt-c-187733',              '--lt-bg-primary-pressed',       3),
    ('--lt-c-fdfdfd',              '--lt-bg-base',                  2),
    ('--lt-c-0668d7',              '--lt-icon-info',                2),
    ('--lt-c-fbfcff',              '--lt-bg-base',                  2),
    ('--lt-c-f6f8fc',              '--lt-bg-base-muted',            2),
    ('--lt-c-e1f4fe',              '--lt-bg-info-muted',            2),
    ('--lt-bg-f7f8f9',             '--lt-bg-base-muted',            2),
    ('--lt-primer-canvas-pale',    '--lt-bg-base-disabled',         2),
    ('--lt-bg-f9f9f9',             '--lt-bg-base-muted',            2),
    ('--lt-c-8b949e',              '--lt-icon-disabled',            2),
    ('--lt-c-25292e',              '--lt-bg-base-inverse',          2),
    ('--lt-c-faf7f9',              '--lt-bg-base-muted',            2),
    ('--lt-c-f3f7fd',              '--lt-bg-base-muted',            1),
    ('--lt-c-f6f6f6',              '--lt-bg-base-muted',            1),
    ('--lt-bg-f7f8',               '--lt-bg-base-muted',            1),
    ('--lt-c-eaecf3',              '--lt-border-disabled',          1),
    ('--lt-c-e7e7ec',              '--lt-bg-base-pressed',          1),
    ('--lt-c-f4f6f8',              '--lt-bg-base-muted',            1),
    ('--lt-c-e5e9ee',              '--lt-bg-base-pressed',          1),
    ('--lt-c-676a75',              '--lt-text-secondary',           1),
    ('--lt-c-ffeded',              '--lt-bg-error-muted',           1),
    ('--lt-c-e7e8ef',              '--lt-bg-base-pressed',          1),
    ('--lt-bg-f5f6f7',             '--lt-bg-base-muted',            1),
    ('--lt-c-cf212e',              '--lt-text-error',               1),
    ('--lt-text-pink',             '--lt-text-purple',              1),
    ('--lt-bg-gray-50',            '--lt-bg-base-muted',            1),
    ('--lt-c-eaecef',              '--lt-bg-base-pressed',          1),
    ('--lt-card-bg',               '--lt-bg-base',                  1),
    ('--lt-bg-f9f9',               '--lt-bg-base-muted',            1),
    ('--lt-bg-eaeb',               '--lt-bg-base-pressed',          1),
    ('--lt-status-info-bg',        '--lt-bg-info-muted',            1),
    ('--lt-status-info-fg',        '--lt-text-info',                1),
    ('--lt-c-f7f9fa',              '--lt-bg-base-muted',            1),
]
HIST_COMMIT = '22e01ae4c'

# Load pre-migration tokens.css for source-token L/D lookup (sources are removed from current).
_PRE_PATH = os.path.join(os.path.dirname(__file__), 'tokens_pre_migration.css')
_pre = open(_PRE_PATH).read() if os.path.exists(_PRE_PATH) else ''
_m = re.search(r':root[^{]*\{(.*?)^\}', _pre, re.S | re.M); _pre_light = _m.group(1) if _m else ''
_m = re.search(r'\[data-color-mode="dark"\][^{]*\{(.*?)^\}', _pre, re.S | re.M); _pre_dark = _m.group(1) if _m else ''
PRE_LIGHT = {n: v.strip() for n, v in re.findall(r'(--lt-[a-z0-9-]+)\s*:\s*([^;]+);', _pre_light)}
PRE_DARK  = {n: v.strip() for n, v in re.findall(r'(--lt-[a-z0-9-]+)\s*:\s*([^;]+);', _pre_dark)}

def swatch(hex_or_value):
    if not hex_or_value: return ''
    h = hex_only(hex_or_value)
    safe = html.escape(str(h))
    return f'<span class="sw" style="background:{safe}"></span>'

# render — only show confirmed REPLACE mappings (REMOVE has no target, PENDING isn't mapped yet)
mapped_tokens = [s for s, v in MAPPINGS.items() if v[0] == 'REPLACE']
total = len(mapped_tokens)
total_uses = sum(usage.get(s, 0) for s in mapped_tokens)
hist_total = sum(n for _, _, n in HISTORICAL_DELTA_SWAPS)

rows = []
# Two sources of mappings combined, each tagged with an origin pill:
#   - "Design team"  — explicit decisions from OrphanTokens.txt; source still in tokens.css today
#   - "Phase 1 Δ≤5"  — automated migration in commit 22e01ae4c; source already removed
items = [(s, v) for s, v in MAPPINGS.items() if v[0] == 'REPLACE']
for src, (action, target, note) in items:
    n = usage.get(src, 0)
    if src.startswith('--lt-c-'):
        src_l, src_d = f'#{src[7:]}', '(same)'
    else:
        src_l, src_d = LIGHT.get(src, '?'), DARK.get(src, '?')
    tgt_l, tgt_d = LIGHT.get(target, '?'), DARK.get(target, '?')
    rows.append({
        'src': src, 'src_l': src_l, 'src_d': src_d,
        'target': target, 'tgt_l': tgt_l, 'tgt_d': tgt_d,
        'note': note, 'uses': n, 'origin': 'design',
    })
for src, target, swaps in HISTORICAL_DELTA_SWAPS:
    src_l = PRE_LIGHT.get(src, '?'); src_d = PRE_DARK.get(src, '?')
    tgt_l = LIGHT.get(target, '?'); tgt_d = DARK.get(target, '?')
    rows.append({
        'src': src, 'src_l': src_l, 'src_d': src_d,
        'target': target, 'tgt_l': tgt_l, 'tgt_d': tgt_d,
        'note': f'commit {HIST_COMMIT[:7]}', 'uses': swaps, 'origin': 'phase1',
    })
rows.sort(key=lambda r: -r['uses'])

ts = datetime.datetime.now().strftime('%Y-%m-%d')

html_out = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Orphan token replacements — DS migration audit</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; padding: 16px 24px; color: #1f2328; font-size: 13px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .meta {{ color: #656d76; font-size: 12px; margin-bottom: 12px; }}
  .nav {{ margin-bottom: 14px; }}
  .nav a {{ font-size: 12px; font-weight: 600; padding: 6px 14px; border-radius: 6px; text-decoration: none; margin-right: 8px; }}
  .nav a.back {{ background: #f6f8fa; color: #054078; border: 1px solid #d0d7de; }}
  .nav a.fwd  {{ background: linear-gradient(135deg, #0969da, #054078); color: white; letter-spacing: 0.3px; }}
  .stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0 16px; }}
  .stat {{ display: inline-flex; align-items: baseline; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 12px; color: #656d76; background: #f6f8fa; border: 1px solid #d0d7de; }}
  .stat .num {{ font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; color: #1f2328; }}
  .stat .num-small {{ font-size: 11px; opacity: 0.7; margin-left: 4px; }}
  .stat.remove {{ background: #ffebe9; border-color: #ffcecb; color: #6a0e1e; }}
  .stat.replace {{ background: #ddf4ff; border-color: #b6e3ff; color: #054078; }}
  .stat.pending {{ background: #fff8c5; border-color: #f1d878; color: #693e00; }}
  .controls {{ margin-bottom: 12px; }}
  .controls input {{ padding: 6px 10px; font-size: 13px; width: 280px; border: 1px solid #d0d7de; border-radius: 6px; }}
  .controls select {{ padding: 6px 10px; font-size: 13px; border: 1px solid #d0d7de; border-radius: 6px; margin-left: 8px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #f6f8fa; text-align: left; padding: 8px 10px; border-bottom: 2px solid #d0d7de; font-weight: 600; position: sticky; top: 0; cursor: pointer; user-select: none; font-size: 12px; }}
  th:hover {{ background: #eaeef2; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #eef0f3; vertical-align: middle; }}
  .sw {{ display: inline-block; width: 28px; height: 18px; border-radius: 3px; border: 1px solid rgba(0,0,0,.2); vertical-align: middle; margin-right: 6px; }}
  .name {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
  .hex {{ font-family: ui-monospace, monospace; font-size: 11px; color: #656d76; }}
  .hex-literal {{ font-family: ui-monospace, monospace; font-size: 12px; color: #1f2328; font-weight: 600; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .pill {{ display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.4px; white-space: nowrap; }}
  .pill.design {{ background: #ddf4ff; color: #054078; }}
  .pill.phase1 {{ background: #fff4ec; color: #7a3300; }}
  td.note {{ color: #656d76; font-size: 11px; max-width: 280px; }}
  .hex-cell {{ display: inline-flex; align-items: center; gap: 4px; }}
</style></head><body>
<div class="nav">
  <a class="back" href="index.html">← Token sheet</a>
  <a class="back" href="mapping.html">Mapping report</a>
  <a class="back" href="c-token-review.html">--lt-c-* review</a>
</div>

<h1>Tokens migration with Δ≤5</h1>
<div class="meta">Audit log of every non-canonical token mapped to a canonical DS equivalent (light delta ≤ 5, Rule 1 compliant) · last generated {ts}</div>

<div class="stats">
  <div class="stat replace"><span class="num">{total}</span> orphan → canonical mappings <span class="num-small">({total_uses:,} refs)</span></div>
  <div class="stat" style="background:#fff4ec; border-color:#fcd0b0; color:#7a3300;"><span class="num">{len(HISTORICAL_DELTA_SWAPS)}</span> Phase 1 migrations <span class="num-small">({hist_total:,} swaps)</span></div>
  <div class="stat"><span class="num">{total + len(HISTORICAL_DELTA_SWAPS)}</span> total tokens <span class="num-small">({total_uses + hist_total:,} refs)</span></div>
</div>

<div class="controls">
  <input id="f" placeholder="Filter token…" oninput="flt()">
  <select id="o" onchange="flt()">
    <option value="">All origins</option>
    <option value="design">Design team only</option>
    <option value="phase1">Phase 1 Δ≤5 only</option>
  </select>
  <span style="font-size:11px; color:#656d76; margin-left:12px;">Click any column header to sort. Hover swatch for hex.</span>
</div>

<table id="t">
<thead><tr>
  <th onclick="sort(0)">Origin</th>
  <th onclick="sort(1)">Source token</th>
  <th onclick="sort(2)">Light</th>
  <th onclick="sort(3)">Dark</th>
  <th></th>
  <th onclick="sort(5)">Target</th>
  <th onclick="sort(6)">Light</th>
  <th onclick="sort(7)">Dark</th>
  <th onclick="sort(8)">Notes</th>
  <th onclick="sort(9)" class="num">Uses</th>
</tr></thead>
<tbody>
"""

for r in rows:
    src_sw = swatch(r['src_l'])
    src_l_display = html.escape(r['src_l'][:24])
    src_d_display = html.escape(r['src_d'][:24])
    src_d_sw = swatch(r['src_d']) if r['src_d'] != '(same)' else swatch(r['src_l'])
    tgt_l_display = html.escape(r['tgt_l'][:24]) if r['tgt_l'] else ''
    tgt_d_display = html.escape(r['tgt_d'][:24]) if r['tgt_d'] else ''
    tgt_l_sw = swatch(r['tgt_l']) if r['tgt_l'] else ''
    tgt_d_sw = swatch(r['tgt_d']) if r['tgt_d'] else ''
    note = html.escape(r['note'])
    src_safe = html.escape(r['src'])
    tgt_safe = html.escape(r['target'])
    origin = r['origin']
    origin_label = 'Design team' if origin == 'design' else 'Phase 1 Δ≤5'
    html_out += f"""<tr data-tok="{src_safe}" data-origin="{origin}">
  <td><span class="pill {origin}">{origin_label}</span></td>
  <td><span class="name">{src_safe}</span></td>
  <td><span class="hex-cell">{src_sw}<span class="hex">{src_l_display}</span></span></td>
  <td><span class="hex-cell">{src_d_sw}<span class="hex">{src_d_display}</span></span></td>
  <td>→</td>
  <td><span class="name">{tgt_safe}</span></td>
  <td><span class="hex-cell">{tgt_l_sw}<span class="hex">{tgt_l_display}</span></span></td>
  <td><span class="hex-cell">{tgt_d_sw}<span class="hex">{tgt_d_display}</span></span></td>
  <td class="note">{note}</td>
  <td class="num">{r['uses']}</td>
</tr>
"""

html_out += """</tbody></table>

<script>
function flt() {
  var f = document.getElementById('f').value.toLowerCase();
  var o = document.getElementById('o').value;
  var rows = document.querySelectorAll('#t tbody tr');
  rows.forEach(function(r) {
    var tok = r.getAttribute('data-tok').toLowerCase();
    var origin = r.getAttribute('data-origin');
    var show = (!f || tok.indexOf(f) >= 0) && (!o || origin === o);
    r.style.display = show ? '' : 'none';
  });
}
function sort(col) {
  var tbody = document.querySelector('#t tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var dir = tbody.getAttribute('data-sort-col') == col && tbody.getAttribute('data-sort-dir') == 'asc' ? 'desc' : 'asc';
  rows.sort(function(a, b) {
    var av = a.cells[col].innerText.trim();
    var bv = b.cells[col].innerText.trim();
    var an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return dir === 'asc' ? an - bn : bn - an;
    return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  tbody.setAttribute('data-sort-col', col);
  tbody.setAttribute('data-sort-dir', dir);
}
</script>
</body></html>
"""

open(OUT, 'w').write(html_out)
print(f"wrote {OUT} ({len(MAPPINGS)} tokens, {total_uses:,} usages, ~{len(html_out)//1024}KB)")
