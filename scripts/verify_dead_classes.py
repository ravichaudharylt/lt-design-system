"""
Second-pass verifier for dead CSS classes.

For each candidate "dead" class found by the first scan:
  - Search for the LITERAL class name (whole word) in all source + CSS files
  - Categorize each hit:
      * styles.X / s.X / cn.X (lib access) → LIVE
      * styles['X'] or similar → LIVE
      * String "X" passed to className= → LIVE
      * Just appears in a comment, unrelated identifier → ambiguous
  - A class is "truly dead" only if zero hits OR all hits are unrelated
"""
import os, re, collections, json

WP = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-web-platform-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-components-dark-mode'

# Parse all CSS module classes (same as first-pass scanner)
all_css_classes = {}  # path → {className: [tokens]}
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dirpath, dirnames, files in os.walk(root):
        if any(p in dirpath for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dirnames[:] = []; continue
        for fn in files:
            if not fn.endswith('.module.css'): continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path) as f: content = f.read()
            except: continue
            cur_class = None; depth = 0
            for line in content.split('\n'):
                m = re.match(r'^\.([a-zA-Z_][\w-]*)\b', line.strip())
                if m and '{' in line:
                    cur_class = m.group(1)
                    depth = line.count('{') - line.count('}')
                    all_css_classes.setdefault(path, {}).setdefault(cur_class, [])
                    for vm in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', line):
                        all_css_classes[path][cur_class].append(vm.group(1))
                elif cur_class and depth > 0:
                    for vm in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', line):
                        all_css_classes[path][cur_class].append(vm.group(1))
                    depth += line.count('{') - line.count('}')
                    if depth <= 0: cur_class = None

# For each class, do exhaustive verification
def is_live_ref(line, idx, classname):
    """Determine if the class name reference at line[idx] looks like a real usage."""
    before = line[max(0, idx-30):idx]
    after = line[idx+len(classname):idx+len(classname)+30]
    # Patterns that indicate live usage
    if re.search(r'styles?\s*\.\s*$|s\s*\.\s*$|cn\s*\.\s*$|cls\s*\.\s*$|css\s*\.\s*$', before): return 'live'
    if re.search(r'styles?\s*\[\s*[\'"]$|s\s*\[\s*[\'"]$|cn\s*\[\s*[\'"]$', before): return 'live'
    # String literal in className= or class="
    if re.search(r'className\s*=\s*[\'"]\s*$|class\s*=\s*[\'"]\s*$', before): return 'live'
    if re.search(r'className.*[\'"]\s*$', before) and re.search(r'^\s*[\'"]', after): return 'live'
    # General: appears inside a quoted string after a className-like attribute
    return None

# Verify each class
truly_dead = []
suspicious = []   # has hits but couldn't classify
import subprocess

for path, classes in all_css_classes.items():
    for cls, tokens in classes.items():
        if not tokens: continue  # skip classes without var() refs
        # Search for whole-word class name across all source files
        r = subprocess.run([
            'grep','-rn','--include=*.tsx','--include=*.ts','--include=*.jsx','--include=*.js',
            '--include=*.html','-w', cls,
            f'{WP}/apps', f'{WP}/packages', f'{LTC}/src',
            '--exclude-dir=node_modules','--exclude-dir=lib','--exclude-dir=dist','--exclude-dir=build','--exclude-dir=stories'
        ], capture_output=True, text=True, timeout=15)
        lines = r.stdout.splitlines()
        has_live = False
        any_hit = bool(lines)
        for hit in lines:
            try: hit_path, hit_line, hit_text = hit.split(':', 2)
            except: continue
            # Find position of class name in line
            idx = hit_text.find(cls)
            if idx < 0: continue
            verdict = is_live_ref(hit_text, idx, cls)
            if verdict == 'live': has_live = True; break
        if not any_hit or not has_live:
            truly_dead.append({'file': path, 'class': cls, 'tokens': tokens, 'hits': len(lines)})

# Compute deletable tokens
import collections
dead_tokens_count = collections.Counter()
for d in truly_dead:
    for t in d['tokens']:
        dead_tokens_count[t] += 1

# Get total ref count for each token from a global scan
token_global_refs = collections.Counter()
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dirpath, dirnames, files in os.walk(root):
        if any(p in dirpath for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dirnames[:] = []; continue
        for fn in files:
            if fn == 'tokens.css': continue
            if not fn.endswith(('.tsx','.ts','.jsx','.js','.css','.scss','.module.css','.html')): continue
            try:
                with open(os.path.join(dirpath, fn)) as f: content = f.read()
            except: continue
            for m in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', content):
                token_global_refs[m.group(1)] += 1

# Tokens whose ENTIRE ref count is inside dead classes
fully_dead_tokens = []
for tok, dead_count in dead_tokens_count.items():
    global_count = token_global_refs.get(tok, 0)
    if global_count > 0 and dead_count >= global_count:
        fully_dead_tokens.append((tok, dead_count))

# Filter out design canonicals
import openpyxl
def canonical(name):
    parts = name.split('/')
    if parts[0] == 'color': parts = parts[1:]
    return '--lt-' + '-'.join(parts)
wb = openpyxl.load_workbook('/Users/ravichaudhary/Downloads/dark-mode-color-audit (1).xlsx', data_only=True)
design_set = set()
section = None
for row in wb['FINAL'].iter_rows(values_only=True):
    a, name, light, dark = row[0], row[1], row[2], row[3]
    if a and not name: section = a; continue
    if name and light and str(name).upper() != 'TOKENS USED IN DESIGN SYSTEM':
        nm = str(name).strip()
        if section == 'ICON' and nm.startswith('color/border/'):
            nm = 'color/icon/' + nm.split('/', 2)[2]
        design_set.add(canonical(nm))

deletable = [(t, n) for t, n in fully_dead_tokens if t not in design_set]
deletable.sort(key=lambda x: -x[1])

print(f"=== Pass-2 verification results ===\n")
print(f"Dead CSS classes (verified by 2-pattern + grep check): {len(truly_dead)}")
print(f"Distinct tokens with refs hiding in dead classes:       {len(dead_tokens_count)}")
print(f"Tokens whose ALL refs are in dead classes:              {len(fully_dead_tokens)}")
print(f"  └─ Of these, non-design canonical (deletable):        {len(deletable)}")
print()
print("=== Top deletable tokens (with dead-class refs) ===")
for t, n in deletable[:20]:
    print(f"  {t:<32}  {n} ref{'s' if n!=1 else ''}")

json.dump({'deletable': [t for t,_ in deletable], 'dead_class_count': len(truly_dead)}, open('/tmp/css_class_deletable.json','w'))
