"""
Surgical per-class revert: for each dead class in each file,
replace only the class's rule block with upstream's version.
Other classes in the file are preserved as-is.
"""
import os, re, json, subprocess

WP = '/Users/ravichaudhary/Desktop/LambdaTest/DarkMode/lt-web-platform-dark-mode'
plan = json.load(open('/tmp/surgical_revert_plan.json'))

def find_class_blocks(content, classname):
    """Find all rule blocks that have `.classname` as the leading selector.
    Returns list of (start_idx, end_idx_after_closing_brace) tuples."""
    blocks = []
    pos = 0
    pat = re.compile(rf'(^|\n)(\.{re.escape(classname)}\b[^{{}}]*)\{{', re.M)
    while True:
        m = pat.search(content, pos)
        if not m: break
        # The rule starts at the '.' of the classname (or after \n)
        start = m.start(2)
        # Find the matching closing brace
        idx = m.end()  # after the opening {
        depth = 1
        while idx < len(content) and depth > 0:
            if content[idx] == '{': depth += 1
            elif content[idx] == '}': depth -= 1
            idx += 1
        blocks.append((start, idx))
        pos = idx
    return blocks

total_reverts = 0
files_modified = 0
for file_path, dead_classes in plan['files'].items():
    # Get upstream version of the file
    rel = file_path.replace(WP+'/','')
    r = subprocess.run(['git','-C',WP,'show', f'upstream/main:{rel}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ✗ not in upstream: {rel}")
        continue
    upstream_content = r.stdout
    try:
        with open(file_path) as f: local_content = f.read()
    except Exception as e:
        print(f"  ✗ can't read {rel}: {e}"); continue

    # For each dead class, replace local's blocks with upstream's blocks
    new_content = local_content
    for cls in dead_classes:
        local_blocks = find_class_blocks(new_content, cls)
        upstream_blocks = find_class_blocks(upstream_content, cls)
        if not local_blocks:
            continue
        if not upstream_blocks:
            # Class not in upstream — keep local but warn
            print(f"  ! .{cls} in {rel} not in upstream — skipping")
            continue
        # Concatenate all upstream blocks for this class
        upstream_block_text = '\n'.join(upstream_content[s:e] for s, e in upstream_blocks)
        # Remove all local blocks (in reverse order to preserve indices), then insert upstream_block_text at the first removed position
        first_start = local_blocks[0][0]
        for start, end in sorted(local_blocks, reverse=True):
            new_content = new_content[:start] + new_content[end:]
        # Now insert the upstream block at first_start
        new_content = new_content[:first_start] + upstream_block_text + new_content[first_start:]
        total_reverts += 1

    if new_content != local_content:
        with open(file_path, 'w') as f: f.write(new_content)
        files_modified += 1
        # Verify no var(--deletable) refs remain for this file
        remaining = sum(1 for t in plan['deletable_tokens']
                       if f'var({t})' in new_content)
        print(f"  ✓ {rel}  ({len(dead_classes)} classes reverted, {remaining} deletable-token refs remain)")

print(f"\nFiles modified: {files_modified}")
print(f"Class reverts: {total_reverts}")
