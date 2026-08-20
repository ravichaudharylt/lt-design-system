"""
Detect CSS module classes that:
  - Are defined in *.module.css files
  - Contain var(--lt-X) references
  - Are NEVER consumed via `styles.X` / `s.X` / template-literal `${styles.X}`
  - The CSS file containing them might still be imported (for other classes that ARE used)
  - But this specific class is dead — so its var() refs are effectively dead

Then identify tokens whose ALL refs land in dead classes.
"""
import os, re, collections

WP = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-web-platform-dark-mode'
LTC = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-components-dark-mode'

# 1. Parse all CSS module files for class definitions + their var() refs
class_to_tokens = collections.defaultdict(lambda: collections.defaultdict(list))
# key1: file path, key2: class name, value: list of tokens

CSS_CLASS_DEF_RE = re.compile(r'^\s*\.([\w-]+)(?:\s*[,>+~]|\s*\{|\s*:|\s*\.[\w-]+)', re.M)
CSS_BLOCK_RE = re.compile(r'\.([\w-]+)\s*[\w\s\-,\.\:\>\+\~\[\]\(\)"\'=]*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', re.S)

for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dirpath, dirnames, files in os.walk(root):
        if any(p in dirpath for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dirnames[:] = []; continue
        for fn in files:
            if not fn.endswith('.module.css'): continue  # only CSS modules
            path = os.path.join(dirpath, fn)
            try:
                with open(path) as f: content = f.read()
            except: continue
            # Simple approach: split by '}' and look for class definitions + var() within each chunk
            # Better: regex match each `.className { ... }` block
            # Use a simpler line-based scan
            cur_class = None
            depth = 0
            for line in content.split('\n'):
                # Detect class start (rough)
                m = re.match(r'^\.([a-zA-Z_][\w-]*)\b', line.strip())
                if m and '{' in line:
                    cur_class = m.group(1)
                    depth = line.count('{') - line.count('}')
                    # Capture vars on same line
                    for vm in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', line):
                        class_to_tokens[path][cur_class].append(vm.group(1))
                elif cur_class and depth > 0:
                    for vm in re.finditer(r'var\((--lt-[a-zA-Z0-9-]+)\)', line):
                        class_to_tokens[path][cur_class].append(vm.group(1))
                    depth += line.count('{') - line.count('}')
                    if depth <= 0: cur_class = None

# 2. Find which CSS classes are consumed (styles.X / s.X / template)
class_usage_count = collections.Counter()
for root in [f"{WP}/apps", f"{WP}/packages", f"{LTC}/src"]:
    for dirpath, dirnames, files in os.walk(root):
        if any(p in dirpath for p in ['/node_modules/','/lib/','/dist/','/build/','/stories/']):
            dirnames[:] = []; continue
        for fn in files:
            if not fn.endswith(('.tsx','.ts','.jsx','.js')): continue
            try:
                with open(os.path.join(dirpath, fn)) as f: content = f.read()
            except: continue
            # patterns: styles.foo / s.foo / styles['foo'] / `${styles.foo}` / 'foo'
            for m in re.finditer(r'(?:styles?|cn|cls|css)\s*\.\s*([a-zA-Z_]\w+)', content):
                class_usage_count[m.group(1)] += 1
            for m in re.finditer(r'(?:styles?|cn|cls|css)\s*\[\s*["\']([a-zA-Z_]\w+)["\']', content):
                class_usage_count[m.group(1)] += 1

# 3. Identify DEAD CSS classes (have var refs but never consumed)
dead_class_token_refs = collections.Counter()
total_dead_classes = 0
dead_class_examples = []
for path, classes in class_to_tokens.items():
    for cls, tokens in classes.items():
        if class_usage_count.get(cls, 0) == 0 and tokens:
            total_dead_classes += 1
            for t in tokens:
                dead_class_token_refs[t] += 1
            if len(dead_class_examples) < 20:
                rel = path.replace(WP+'/', '').replace(LTC+'/', '~ltc/')
                dead_class_examples.append((rel, cls, tokens[:3]))

print(f"Dead CSS-module classes with var(--lt-X) refs: {total_dead_classes}")
print(f"Total dead-class token refs: {sum(dead_class_token_refs.values())}")
print(f"Distinct tokens affected: {len(dead_class_token_refs)}")
print()
print("=== Sample dead classes ===")
for path, cls, toks in dead_class_examples[:15]:
    print(f"  .{cls} in {path}")
    print(f"     uses: {', '.join(toks[:3])}{'...' if len(toks) > 3 else ''}")

# Save for cross-check with global token usage
import json
json.dump({
    'class_refs_per_token': dict(dead_class_token_refs),
    'dead_classes_count': total_dead_classes,
}, open('/tmp/dead_classes.json','w'))
PY
