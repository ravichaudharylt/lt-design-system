"""Surgically revert verified-dead css-module classes to upstream/main.

IN-PLACE version: each rule block is replaced at its original position,
matched to upstream by exact selector. No consolidation, no reordering.
"""
import os, re, json, subprocess

WP = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-web-platform-dark-mode'
plan = json.load(open('/tmp/dead_c_classes_plan.json'))

def find_class_blocks(content, classname):
    """Return [(start, end, selector)] for every rule block whose leading
    selector starts with `.classname` (incl. `.classname:hover`, descendant
    selectors, etc). selector is whitespace-normalized for matching."""
    blocks = []
    pat = re.compile(rf'(^|\n)([ \t]*)(\.{re.escape(classname)}\b[^{{}}]*)\{{', re.M)
    pos = 0
    while True:
        m = pat.search(content, pos)
        if not m:
            break
        start = m.start(3)
        selector = ' '.join(m.group(3).split())  # normalize whitespace
        idx = m.end()
        depth = 1
        while idx < len(content) and depth > 0:
            if content[idx] == '{':
                depth += 1
            elif content[idx] == '}':
                depth -= 1
            idx += 1
        blocks.append((start, idx, selector))
        pos = idx
    return blocks

total_classes = 0
total_files = 0
total_blocks = 0
not_in_upstream = []
no_upstream_match = []

for file_path, dead_classes in plan['files'].items():
    rel = file_path.replace(WP + '/', '')
    r = subprocess.run(['git', '-C', WP, 'show', f'upstream/main:{rel}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  x not in upstream: {rel}")
        continue
    upstream_content = r.stdout
    try:
        local_content = open(file_path).read()
    except Exception as e:
        print(f"  x cant read {rel}: {e}")
        continue

    new_content = local_content
    reverted_here = 0
    blocks_here = 0

    for cls in dead_classes:
        local_blocks = find_class_blocks(new_content, cls)
        up_blocks = find_class_blocks(upstream_content, cls)
        if not local_blocks:
            continue
        if not up_blocks:
            not_in_upstream.append((rel, cls))
            continue

        # upstream blocks grouped by selector, in document order (a FIFO queue)
        up_by_sel = {}
        for s, e, sel in up_blocks:
            up_by_sel.setdefault(sel, []).append(upstream_content[s:e])

        # match each local block to an upstream block of the SAME selector,
        # consuming in document order; build in-place replacements
        consumed = {}
        replacements = []  # (start, end, new_text)
        for s, e, sel in sorted(local_blocks, key=lambda b: b[0]):
            queue = up_by_sel.get(sel, [])
            idx = consumed.get(sel, 0)
            if idx < len(queue):
                replacements.append((s, e, queue[idx]))
                consumed[sel] = idx + 1
            else:
                # no upstream block with this exact selector — leave local as-is
                no_upstream_match.append((rel, sel))

        if not replacements:
            continue
        # apply in reverse start order so earlier indices stay valid
        for s, e, txt in sorted(replacements, key=lambda r: -r[0]):
            new_content = new_content[:s] + txt + new_content[e:]
        reverted_here += 1
        blocks_here += len(replacements)
        total_classes += 1
        total_blocks += len(replacements)

    if new_content != local_content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        total_files += 1
        leftover = sum(1 for t in plan['tokens_in_dead']
                       if f'var({t})' in new_content)
        print(f"  ok {rel}  ({reverted_here} classes, {blocks_here} blocks in-place, "
              f"{leftover} plan-token refs remain)")

print(f"\nFiles modified: {total_files}")
print(f"Classes reverted: {total_classes}")
print(f"Rule blocks replaced in-place: {total_blocks}")
if not_in_upstream:
    print(f"\nClasses NOT in upstream (skipped): {len(not_in_upstream)}")
    for rel, cls in not_in_upstream:
        print(f"  .{cls}  ({rel})")
if no_upstream_match:
    print(f"\nLocal selectors with no upstream match (left as-is): {len(no_upstream_match)}")
    for rel, sel in no_upstream_match[:15]:
        print(f"  {sel}  ({rel})")
