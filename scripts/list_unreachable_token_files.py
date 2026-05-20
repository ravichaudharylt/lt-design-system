"""List unreachable files that contain non-design-canonical (orphan) token usages.

These are dead-code files — candidates for whole-file revert to upstream/main.
Groups by product/package and reports per-file orphan-token usage counts.
"""
import os, re, json, collections, subprocess

WP = '/Users/ravichaudhary/Desktop/LambdaTest/lt-web-platform-worktrees/feat-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components'
TOKENS_CSS = f'{LTC}/src/styles/tokens.css'
XLSX = '/Users/ravichaudhary/Downloads/dark-mode-color-audit (1).xlsx'

# design canonical set (exclude)
import openpyxl
def canonical(name):
    parts = name.split('/')
    if parts[0] == 'color': parts = parts[1:]
    return '--lt-' + '-'.join(parts)
design_set = set()
wb = openpyxl.load_workbook(XLSX, data_only=True)
section = None
for row in wb['FINAL'].iter_rows(values_only=True):
    a, name, light, dark = row[0], row[1], row[2], row[3]
    if a and not name: section = a; continue
    if name and light and str(name).upper() != 'TOKENS USED IN DESIGN SYSTEM':
        nm = str(name).strip()
        if section == 'ICON' and nm.startswith('color/border/'):
            nm = 'color/icon/' + nm.split('/', 2)[2]
        design_set.add(canonical(nm))

defined = set(re.findall(r'(--lt-[a-zA-Z0-9-]+)\s*:', open(TOKENS_CSS).read()))
scope = defined - design_set

reachable = set(json.load(open('/tmp/reachability_v3.json'))['reachable'])

# Walk source, find files NOT in reachable that use scope tokens
file_token_uses = collections.defaultdict(collections.Counter)
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dp, dns, fns in os.walk(root):
        if any(p in dp for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dns[:] = []; continue
        for fn in fns:
            if not fn.endswith(('.tsx','.ts','.jsx','.js','.css','.scss','.html')): continue
            path = os.path.join(dp, fn)
            if path == TOKENS_CSS: continue
            if path in reachable: continue   # only UNREACHABLE files
            try: c = open(path).read()
            except: continue
            for m in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', c):
                if m.group(1) in scope:
                    file_token_uses[path][m.group(1)] += 1

# Only files that actually exist in upstream/main (revertable)
revertable = {}
not_in_upstream = []
for path in file_token_uses:
    rel = path.replace(WP+'/','').replace(LTC+'/','')
    base = WP if path.startswith(WP) else LTC
    chk = subprocess.run(['git','-C',base,'cat-file','-e',f'upstream/main:{rel}'],
                         capture_output=True)
    if chk.returncode == 0:
        revertable[path] = file_token_uses[path]
    else:
        not_in_upstream.append(path)

# Group by product/package
def group_of(path):
    rel = path.replace(WP+'/','').replace(LTC+'/','lt-components/')
    if rel.startswith('apps/'): return rel.split('/')[1]
    if rel.startswith('packages/'): return rel.split('/')[1]
    if rel.startswith('lt-components'): return 'lt-components'
    return 'other'

groups = collections.defaultdict(list)
for path, toks in revertable.items():
    groups[group_of(path)].append((path, sum(toks.values()), len(toks)))

total_files = len(revertable)
total_uses = sum(sum(t.values()) for t in revertable.values())
print(f"=== Unreachable files with orphan-token usages ===\n")
print(f"Revertable files (exist in upstream/main): {total_files}")
print(f"Total orphan-token usages in them:         {total_uses}")
print(f"Files NOT in upstream (can't revert, skip): {len(not_in_upstream)}\n")
for grp in sorted(groups, key=lambda g: -sum(u for _,u,_ in groups[g])):
    files = groups[grp]
    guses = sum(u for _,u,_ in files)
    print(f"  {grp}:  {len(files)} files, {guses} orphan-token usages")

# Save the revert plan
json.dump({
    'files': sorted(revertable.keys()),
    'not_in_upstream': not_in_upstream,
}, open('/tmp/unreachable_revert_plan.json','w'), indent=1)
print(f"\nPlan saved: /tmp/unreachable_revert_plan.json")

# Show top 25 files by usage count
flat = sorted(((p, sum(t.values())) for p,t in revertable.items()), key=lambda x:-x[1])
print(f"\nTop 25 files by orphan-token usage count:")
for p, u in flat[:25]:
    rel = p.replace(WP+'/','').replace(LTC+'/','lt-components/')
    print(f"  {u:>4}  {rel}")
