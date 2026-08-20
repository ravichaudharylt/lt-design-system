"""
Per-product audit: list tokens with ≤ N uses in a single product, with file-by-file
context (line, CSS property, reachability) for review.

Usage: python3 audit_product.py <product> <threshold>
       e.g. python3 audit_product.py magic-leap-dashboard 5
"""
import os, re, sys, json, collections

PRODUCT = sys.argv[1] if len(sys.argv) > 1 else 'magic-leap-dashboard'
THRESHOLD = int(sys.argv[2]) if len(sys.argv) > 2 else 5

WP = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-web-platform-dark-mode'
APP_DIR = f'{WP}/apps/{PRODUCT}'
APP_SRC = f'{APP_DIR}/src'

# 1. Build reachable set for this product
IMPORT_RE = re.compile(r'''(?:^|[\s;])(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]''', re.M)
REQUIRE_RE = re.compile(r'''require\s*\(\s*['"]([^'"]+)['"]\s*\)''')
DYNAMIC_RE = re.compile(r'''import\s*\(\s*['"]([^'"]+)['"]\s*\)''')
EXTS = ['', '.tsx', '.ts', '.jsx', '.js', '.css', '.scss', '.module.css', '/index.tsx', '/index.ts', '/index.jsx', '/index.js']

def resolve(spec, importer_file, src_root):
    if spec.startswith('@lt-web-platform/'): return None  # external workspace
    if spec.startswith('.') or spec.startswith('/'):
        base = os.path.normpath(os.path.join(os.path.dirname(importer_file), spec))
    elif not spec.startswith('@') and not spec.startswith('react') and '/' in spec.split('/')[0]:
        return None
    else:
        # try absolute from src root
        base = os.path.join(src_root, spec)
    for ext in EXTS:
        cand = base + ext
        if os.path.isfile(cand): return cand
    return None

def find_entry():
    for ext in ['.tsx', '.ts', '.jsx', '.js']:
        p = f'{APP_SRC}/index{ext}'
        if os.path.isfile(p): return p
    return None

def parse_imports(content):
    out = set()
    for m in IMPORT_RE.finditer(content): out.add(m.group(1))
    for m in REQUIRE_RE.finditer(content): out.add(m.group(1))
    for m in DYNAMIC_RE.finditer(content): out.add(m.group(1))
    return out

entry = find_entry()
if not entry: print(f"No entry found for {PRODUCT}"); sys.exit(1)

queue = [entry]; reachable = {entry}
while queue:
    cur = queue.pop()
    try: content = open(cur, errors='replace').read()
    except: continue
    for spec in parse_imports(content):
        spec = spec.split('?')[0].split('!')[-1]
        resolved = resolve(spec, cur, APP_SRC)
        if resolved and resolved not in reachable:
            reachable.add(resolved); queue.append(resolved)

print(f"Product: {PRODUCT}")
print(f"Reachable files from entry: {len(reachable)}")

# 2. Walk all product files; collect token refs
def property_of(before):
    if re.search(r'background-color\s*:\s*[^;]*$', before, re.I): return 'bg'
    if re.search(r'background[a-z-]*\s*:\s*[^;]*$', before, re.I): return 'bg'
    if re.search(r'border-(top|right|bottom|left)?(-color)?\s*:\s*[^;]*$', before, re.I): return 'border'
    if re.search(r'border\s*:\s*[^;]*$', before, re.I): return 'border'
    if re.search(r'\boutline\s*:\s*[^;]*$', before, re.I): return 'border'
    if re.search(r'box-shadow\s*:\s*[^;]*$', before, re.I): return 'shadow'
    if re.search(r'\bcolor\s*:\s*[^;]*$', before, re.I): return 'text'
    if re.search(r'\bfill\s*[:=]\s*[^;]*$', before, re.I): return 'fill'
    if re.search(r'\bstroke\s*[:=]\s*[^;]*$', before, re.I): return 'stroke'
    if re.search(r'\bbackgroundColor\s*:\s*[\'"`][^"\'`]*$', before): return 'bg'
    if re.search(r'\bborderColor\s*:\s*[\'"`][^"\'`]*$', before): return 'border'
    if re.search(r'\bcolor\s*[:=]\s*[\'"`][^"\'`]*$', before): return 'text'
    if re.search(r'\bfill\s*=\s*[\'"`{][^\'"`}]*$', before): return 'fill'
    if re.search(r'\bstroke\s*=\s*[\'"`{][^\'"`}]*$', before): return 'stroke'
    return '?'

token_refs = collections.defaultdict(list)
all_files = []
for dirpath, dirnames, files in os.walk(APP_SRC):
    if any(p in dirpath for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
        dirnames[:] = []; continue
    for fn in files:
        if not fn.endswith(('.tsx','.ts','.jsx','.js','.css','.scss','.module.css')): continue
        all_files.append(os.path.join(dirpath, fn))

print(f"Total source files in {PRODUCT}: {len(all_files)}")

for path in all_files:
    try: content = open(path).read()
    except: continue
    for m in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', content):
        tok = m.group(1)
        line_start = content.rfind('\n', 0, m.start()) + 1
        line_end = content.find('\n', m.end())
        if line_end < 0: line_end = len(content)
        line_no = content[:m.start()].count('\n') + 1
        line_content = content[line_start:line_end]
        before = content[line_start:m.start()]
        token_refs[tok].append({
            'file': path, 'line': line_no, 'content': line_content.strip()[:160],
            'prop': property_of(before),
            'reachable': path in reachable,
        })

# 3. Filter to tokens with ≤ THRESHOLD uses
low_usage = {t: refs for t, refs in token_refs.items() if len(refs) <= THRESHOLD}
print(f"\nTokens with ≤ {THRESHOLD} uses in {PRODUCT}: {len(low_usage)}")

# 4. Write markdown report
report_path = f'/tmp/audit_{PRODUCT}.md'
with open(report_path, 'w') as out:
    out.write(f"# Audit — {PRODUCT}\n\n")
    out.write(f"**Threshold**: tokens with ≤ {THRESHOLD} uses in this product\n\n")
    out.write(f"**Reachable files from entry**: {len(reachable)} / {len(all_files)}\n\n")
    out.write(f"**Tokens matching threshold**: {len(low_usage)}\n\n")

    # Sort by usage count, then name
    sorted_tokens = sorted(low_usage.items(), key=lambda kv: (len(kv[1]), kv[0]))
    for tok, refs in sorted_tokens:
        # Reachability summary
        n_reach = sum(1 for r in refs if r['reachable'])
        n_dead = len(refs) - n_reach
        status = ''
        if n_reach == 0: status = ' 💀 ALL refs in unreachable files'
        elif n_dead > 0: status = f' ⚠️ {n_dead}/{len(refs)} refs in unreachable files'

        out.write(f"## `{tok}` — {len(refs)} use{'s' if len(refs)!=1 else ''}{status}\n\n")
        for r in refs:
            rel = r['file'].replace(WP, '~')
            reach_marker = '✓' if r['reachable'] else '✗'
            out.write(f"- `{reach_marker}` **`{rel}:{r['line']}`** _(prop: {r['prop']})_\n")
            out.write(f"  ```\n  {r['content']}\n  ```\n")
        out.write("\n")

print(f"\nReport written to: {report_path}")
print(f"Open it for review.\n")

# Quick summary in stdout
print(f"=== Quick stats ===")
buckets = collections.Counter()
for refs in low_usage.values():
    n_reach = sum(1 for r in refs if r['reachable'])
    if n_reach == 0: buckets['all-dead'] += 1
    elif n_reach < len(refs): buckets['some-dead'] += 1
    else: buckets['all-reachable'] += 1
for k, n in buckets.items(): print(f"  {k}: {n}")
