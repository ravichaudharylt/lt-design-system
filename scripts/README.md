# Dark Mode Token Scripts

Generators and analysis tools for the dark-mode token cleanup. These produce the
HTML dashboards published in this repo (GitHub Pages).

## Build scripts (generate the published dashboards)

| Script | Generates | Published as |
|---|---|---|
| `build_token_sheet.py` | `dark-mode-reports/token_sheet.html` | `index.html` |
| `build_dashboards.py` | `dark-mode-reports/token_mapping.html` | `mapping.html` |
| `build_c_token_review_sheet.py` | `dark-mode-reports/c_token_review.html` | `c-token-review.html` |
| `build_token_review_sheet.py` | `dark-mode-reports/token_review.html` | `token-review.html` |

## Analysis / cleanup tools

| Script | Purpose |
|---|---|
| `reachability_v4.py` | Import-graph BFS from app entries → reachable file set. Handles workspace `dist/`→`src/` remap, `@/` alias, `.svg`. Writes `/tmp/reachability_v4.json`. |
| `collect_dead_c_classes.py` | 2-pass detect dead CSS-module classes holding `--lt-c-*` tokens. |
| `revert_dead_c_classes.py` | Surgical in-place per-class revert to upstream/main (no block reordering). |
| `list_unreachable_token_files.py` | List unreachable files with orphan-token usages (revert candidates). |
| `audit_product.py` | Per-product low-usage token audit with reachability. |
| `verify_dead_classes.py` | Two-pass dead-class verifier (pattern + literal grep). |
| `surgical_revert.py` | Earlier per-class revert (superseded by `revert_dead_c_classes.py`). |
| `scan_unused_css_classes.py` | Find CSS-module classes never consumed via `styles.X`. |

## Hard-coded paths (update if your checkout differs)

- `TOKENS_CSS` → `lt-components/src/styles/tokens.css` (overridable via the
  `TOKENS_CSS` env var, e.g. a `git show <sha>:src/styles/tokens.css` extract or
  the `/tmp/lt-components-mirror` checkout). Must be at the TE-13484 tip or newer.
- `WP` → `lt-web-platform-worktrees/feat-dark-mode`

## Live sources (no xlsx)

The design palette is derived at build time: every token declared in `tokens.css`
that is not listed in `data/orphan_tokens.json` is an official design token; hexes
come straight from `tokens.css`. `data/orphan_tokens.json` holds every known
orphan token name: col A of the "Design Team Review" Google Sheet (324 rows) plus
zero-usage orphans removed from review while still declared in tokens.css
(currently `--lt-accent-brand`, `--lt-primer-danger-muted`). Drop a name from the
list only once its declaration is gone from tokens.css; re-export from the sheet
if orphans are added there. `data/design_palette_names.json` supplies
display slash-names and section labels; a palette token missing from it falls back
to a name derived from its var name.

## Usage

```bash
python3 scripts/build_token_sheet.py     # -> dark-mode-reports/token_sheet.html
python3 scripts/build_dashboards.py       # -> dark-mode-reports/token_mapping.html
# then copy into this repo:
cp ~/Desktop/LambdaTest/dark-mode-reports/token_sheet.html   ./index.html
cp ~/Desktop/LambdaTest/dark-mode-reports/token_mapping.html ./mapping.html
git add -A && git commit -m "Refresh dashboards" && git push
```

> Recovered from the Claude session jsonl after `/tmp` was wiped (2026-05-20).
> Replayed Write+Edit history; fixed the stale xlsx path (97→114 design tokens).
