"""Reachability v4 — fixes workspace-package dist/ traversal.

v3 bug: packages/X/index.js imports from './dist/...'; BFS excludes dist/, so
the package src/ tree was never traversed (0% reachable for all 3 packages).

v4 fix: when an import resolves into packages/<pkg>/dist/<sub>, remap to
packages/<pkg>/src/<sub> and resolve there (dist is built FROM src).
"""
import os, re, json, collections

WP = '/Users/ravichaudhary/Desktop/LambdaTest/lt-web-platform-worktrees/feat-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/lt-components'

IMPORT_RE = re.compile(r'''(?:^|[\s;])(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]''', re.M)
REQUIRE_RE = re.compile(r'''require\s*\(\s*['"]([^'"]+)['"]\s*\)''')
DYNAMIC_RE = re.compile(r'''import\s*\(\s*['"]([^'"]+)['"]\s*\)''')
CSS_IMPORT_RE = re.compile(r'''@import\s+(?:url\()?['"]([^'"]+)['"]\)?''')
EXTS = ['', '.tsx', '.ts', '.jsx', '.js', '.css', '.scss', '.module.css', '.svg',
        '/index.tsx', '/index.ts', '/index.jsx', '/index.js']

WS_PKG_MAP = {
    '@lt-web-platform/test-page-app': f'{WP}/packages/TestPageApp',
    '@lt-web-platform/test-page-web': f'{WP}/packages/TestPageWeb',
    '@lt-web-platform/test-page-components': f'{WP}/packages/TestPageComponents',
}

def remap_dist_to_src(path):
    """packages/<pkg>/dist/<sub>  ->  packages/<pkg>/src/<sub>"""
    m = re.match(rf'({re.escape(WP)}/packages/[^/]+)/dist/(.*)', path)
    if m:
        return f'{m.group(1)}/src/{m.group(2)}'
    return path

def try_exts(base):
    # try src/ remap FIRST (we want source, not built dist/), then the original
    for cand in (remap_dist_to_src(base), base):
        # 1. as-is + appended extensions
        for ext in EXTS:
            p = cand + ext
            if os.path.isfile(p):
                return p
        # 2. strip existing js/ts extension then retry (handles dist .js -> src .jsx)
        stem, ext0 = os.path.splitext(cand)
        if ext0 in ('.js', '.jsx', '.ts', '.tsx'):
            for ext in EXTS:
                p = stem + ext
                if os.path.isfile(p):
                    return p
    return None

def resolve(spec, importer, src_root):
    # workspace package
    for pkg, pkg_root in WS_PKG_MAP.items():
        if spec == pkg:
            # package main entry — read package.json main, else index.js
            for cand in [f'{pkg_root}/index.js', f'{pkg_root}/index.tsx',
                         f'{pkg_root}/src/index.js', f'{pkg_root}/src/index.tsx']:
                if os.path.isfile(cand): return cand
            return None
        if spec.startswith(pkg + '/'):
            sub = spec[len(pkg)+1:]
            # try src/ first (we care about source), then root, then dist->src
            for basedir in (f'{pkg_root}/src', pkg_root, f'{pkg_root}/dist'):
                r = try_exts(os.path.join(basedir, sub))
                if r: return r
            return None
    # relative
    if spec.startswith('.'):
        base = os.path.normpath(os.path.join(os.path.dirname(importer), spec))
        return try_exts(base)
    # absolute
    if spec.startswith('/'):
        return try_exts(spec)
    # path alias: @/ (kaneai = literal src/@/ dir; hyperexecute = cliGui alias)
    # distinct from @scope/pkg npm packages (which have text between @ and /)
    if spec.startswith('@/'):
        sub = spec[2:]
        for base in (os.path.join(src_root, '@', sub),
                     os.path.join(src_root, 'pages/cliGui/src', sub),
                     os.path.join(src_root, sub)):
            r = try_exts(base)
            if r: return r
        return None
    # scoped external package (@primer/react, @lambdatestincprivate/..., @tanstack/...)
    if spec.startswith('@'):
        return None
    # bare module -> absolute-from-src
    return try_exts(os.path.join(src_root, spec))

def parse_imports(content, is_css=False):
    out = set()
    for m in IMPORT_RE.finditer(content): out.add(m.group(1))
    for m in REQUIRE_RE.finditer(content): out.add(m.group(1))
    for m in DYNAMIC_RE.finditer(content): out.add(m.group(1))
    if is_css:
        for m in CSS_IMPORT_RE.finditer(content): out.add(m.group(1))
    return out

def src_root_for(path):
    parts = path.split('/')
    for i in range(len(parts), 0, -1):
        c = '/'.join(parts[:i])
        if c.endswith('/src') and (f'{WP}/apps/' in c or f'{WP}/packages/' in c or f'{LTC}/src' == c):
            return c
    # package root (no /src) — fall back to the package dir
    for i in range(len(parts), 0, -1):
        c = '/'.join(parts[:i])
        if re.match(rf'{re.escape(WP)}/packages/[^/]+$', c):
            return c + '/src'
    return None

entries = [
    f'{WP}/apps/hyperexecute/src/index.js',
    f'{WP}/apps/magic-leap-dashboard/src/index.js',
    f'{WP}/apps/kaneai-test-management-client/src/index.tsx',
    f'{WP}/apps/mobile-web-client/src/index.js',
]
reachable = set()
for entry in entries:
    if not os.path.isfile(entry):
        print(f"  ! missing entry {entry}"); continue
    queue = [entry]
    while queue:
        f = queue.pop()
        if f in reachable: continue
        reachable.add(f)
        try: c = open(f).read()
        except: continue
        is_css = f.endswith(('.css','.scss','.module.css'))
        sr = src_root_for(f)
        if not sr: continue
        for spec in parse_imports(c, is_css):
            tgt = resolve(spec, f, sr)
            if tgt and tgt not in reachable:
                queue.append(tgt)
    app = os.path.basename(os.path.dirname(os.path.dirname(entry)))
    print(f"  after {app}: reachable = {len(reachable)}")

print(f"\nTotal reachable: {len(reachable)}")

# per-area coverage
def cov(prefix):
    total=reach=0
    for dp,dns,fns in os.walk(f'{WP}/{prefix}'):
        if any(p in dp for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dns[:]=[]; continue
        for fn in fns:
            if not fn.endswith(('.tsx','.ts','.jsx','.js','.css','.scss','.module.css')): continue
            total+=1
            if os.path.join(dp,fn) in reachable: reach+=1
    return total,reach
print()
for pfx in ['packages/TestPageApp/src','packages/TestPageWeb/src','packages/TestPageComponents/src',
            'apps/mobile-web-client/src','apps/hyperexecute/src',
            'apps/kaneai-test-management-client/src','apps/magic-leap-dashboard/src']:
    t,r = cov(pfx)
    print(f"  {pfx:<45} {r:>5}/{t:<5} ({(r/t*100 if t else 0):.0f}%)")

json.dump({'reachable': sorted(reachable)}, open('/tmp/reachability_v4.json','w'))
print(f"\nSaved: /tmp/reachability_v4.json")
