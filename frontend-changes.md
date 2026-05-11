# Frontend Changes

## Code Quality Tooling

### What was added

**Prettier** — automatic formatter for HTML, CSS, and JavaScript (the frontend equivalent of Black).

| File | Purpose |
|------|---------|
| `package.json` | Declares Prettier as a dev dependency; defines `format` and `format:check` npm scripts |
| `.prettierrc` | Prettier config: 100-char line width, 2-space indent, LF line endings, CSS whitespace sensitivity |
| `.prettierignore` | Excludes `node_modules/` and already-minified files from formatting |
| `frontend-quality.sh` | Dev script that runs Prettier check + warns about `console.log` in JS |

### npm scripts

```bash
npm run format        # auto-format all files under frontend/
npm run format:check  # check formatting without writing (CI-friendly)
npm run quality       # alias for format:check
```

### Quality check script

```bash
./frontend-quality.sh
```

Runs two checks:
1. Prettier formatting validation across `frontend/`
2. Scan for leftover `console.log` statements in `script.js` (warns, does not fail)

### Files formatted

`frontend/index.html`, `frontend/style.css`, and `frontend/script.js` were run through Prettier on setup and are now consistently formatted.

### .gitignore update

Added `node_modules/` and `package-lock.json` to `.gitignore` so tooling artifacts are not committed.

### Known warnings (not errors)

`frontend/script.js` lines 169 and 174 contain `console.log` calls used for debug logging in `loadCourseStats()`. These are flagged by the quality script but do not fail the check.
