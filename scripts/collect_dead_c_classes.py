"""Collect & 2-pass-verify DEAD css-module classes that hold --lt-c-* tokens.

Pass 1: class defined in *.module.css, has var(--lt-c-*), never consumed via
        styles.X / styles['X'] anywhere.
Pass 2: literal whole-word grep of the class name across all source — if it
        appears in a className string / styles access we missed, it's LIVE.

Output: /tmp/dead_c_classes_plan.json
  { files: { path: [classnames...] }, tokens_in_dead: [--lt-c-*...] }
"""
import os, re, json, collections, subprocess

WP = '/Users/ravichaudhary/Desktop/LambdaTest/lt-web-platform-worktrees/feat-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components'

# 1. Parse all *.module.css → {path: {class: [tokens]}}, line-based brace tracking
mod_classes = {}
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dp, dns, fns in os.walk(root):
        if any(p in dp for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dns[:] = []; continue
        for fn in fns:
            if not fn.endswith('.module.css'): continue
            path = os.path.join(dp, fn)
            try: content = open(path).read()
            except: continue
            cur = None; depth = 0
            for line in content.split('\n'):
                m = re.match(r'^\s*\.([a-zA-Z_][\w-]*)\b', line)
                if m and '{' in line:
                    cur = m.group(1)
                    depth = line.count('{') - line.count('}')
                    mod_classes.setdefault(path, {}).setdefault(cur, [])
                    for vm in re.finditer(r'var\((--lt-c-[a-zA-Z0-9-]+)\)', line):
                        mod_classes[path][cur].append(vm.group(1))
                elif cur and depth > 0:
                    for vm in re.finditer(r'var\((--lt-c-[a-zA-Z0-9-]+)\)', line):
                        mod_classes[path][cur].append(vm.group(1))
                    depth += line.count('{') - line.count('}')
                    if depth <= 0: cur = None

# 2. Build global class-consumption map (pass 1)
consumed = collections.Counter()
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dp, dns, fns in os.walk(root):
        if any(p in dp for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dns[:] = []; continue
        for fn in fns:
            if not fn.endswith(('.tsx','.ts','.jsx','.js')): continue
            try: c = open(os.path.join(dp, fn)).read()
            except: continue
            for m in re.finditer(r'(?:styles?|cn|cls|css)\s*\.\s*([a-zA-Z_]\w+)', c):
                consumed[m.group(1)] += 1
            for m in re.finditer(r'(?:styles?|cn|cls|css)\s*\[\s*["\']([a-zA-Z_]\w+)["\']', c):
                consumed[m.group(1)] += 1

# 3. Candidate dead classes: have --lt-c-* tokens AND consumed count == 0
candidates = []  # (path, class, tokens)
for path, classes in mod_classes.items():
    for cls, toks in classes.items():
        if toks and consumed.get(cls, 0) == 0:
            candidates.append((path, cls, toks))

print(f"Pass-1 dead-class candidates (have --lt-c-*, never via styles.X): {len(candidates)}")

# 4. Pass-2: literal whole-word grep for each candidate class name
verified_dead = []
suspicious = []
for path, cls, toks in candidates:
    r = subprocess.run(
        ['grep','-rlw','--include=*.tsx','--include=*.ts','--include=*.jsx',
         '--include=*.js','--include=*.html', cls,
         f'{WP}/apps', f'{WP}/packages', f'{LTC}/src',
         '--exclude-dir=node_modules','--exclude-dir=lib','--exclude-dir=dist',
         '--exclude-dir=build','--exclude-dir=stories'],
        capture_output=True, text=True, timeout=20)
    hits = [h for h in r.stdout.strip().split('\n') if h]
    if not hits:
        verified_dead.append((path, cls, toks))
    else:
        # appears literally somewhere — keep for manual review unless hits are unrelated
        suspicious.append((path, cls, toks, hits))

print(f"Pass-2 verified DEAD (zero literal whole-word hits): {len(verified_dead)}")
print(f"Pass-2 suspicious (has literal hits — needs review): {len(suspicious)}")

# 5. Group verified-dead by file
plan_files = collections.defaultdict(list)
tokens_in_dead = collections.Counter()
for path, cls, toks in verified_dead:
    plan_files[path].append(cls)
    for t in toks: tokens_in_dead[t] += 1

json.dump({
    'files': {p: sorted(set(cs)) for p, cs in plan_files.items()},
    'tokens_in_dead': dict(tokens_in_dead),
    'suspicious': [{'file': p, 'class': c, 'tokens': t, 'hits': h[:5]}
                   for p, c, t, h in suspicious],
}, open('/tmp/dead_c_classes_plan.json', 'w'), indent=1)

print()
print(f"Files with verified-dead classes: {len(plan_files)}")
print(f"Distinct --lt-c-* tokens inside verified-dead classes: {len(tokens_in_dead)}")
print()
print("Sample verified-dead classes:")
for path, cls, toks in verified_dead[:20]:
    rel = path.replace(WP+'/','').replace(LTC+'/','lt-components/')
    print(f"  .{cls}  in  {rel}")
    print(f"     tokens: {', '.join(sorted(set(toks)))}")
print()
print("Plan saved: /tmp/dead_c_classes_plan.json")
