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

---

## Dark/Light Mode Toggle Button

### Summary

Added a sun/moon theme toggle button to the bottom of the left sidebar that switches between the existing dark theme and a new light theme, with smooth animated transitions and localStorage persistence.

### Files Modified

#### `frontend/index.html`
- Added an inline `<script>` in `<head>` that applies `light-theme` class to `<html>` immediately on load (prevents flash of wrong theme on page refresh).
- Added `div.sidebar-footer` at the bottom of `aside.sidebar` containing `button#themeToggle.theme-toggle` with two inline SVGs: `.icon-sun` (shown in dark mode) and `.icon-moon` (shown in light mode). Both SVGs have `aria-hidden="true"`; the button itself carries `aria-label="Toggle light/dark mode"`.

#### `frontend/style.css`
- Added a second `*, *::before, *::after` rule with `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease` for smooth theme-switching across all elements.
- Added `html.light-theme { ... }` block that overrides all dark-theme CSS custom properties with light equivalents.
- Added `display: flex; flex-direction: column` to `.sidebar` so `.sidebar-footer` can use `margin-top: auto` to stick to the bottom.
- Added `.sidebar-footer` styles: `margin-top: auto`, `padding-top: 1.25rem`, `border-top` separator.
- Added `.theme-toggle` button styles: 40×40px circle, no background, `--text-secondary` color, hover changes to `--primary-color` with a blue tint background.

#### `frontend/script.js`
- Inside `setupEventListeners()`, added a click handler on `#themeToggle` that toggles `light-theme` on `<html>` and persists the preference to `localStorage`.

### Accessibility
- Button is a native `<button>` element — keyboard-navigable out of the box.
- `aria-label="Toggle light/dark mode"` provides screen-reader context.
- SVG icons have `aria-hidden="true"` so they are not read redundantly.
- Focus ring via `:focus-visible` (consistent with existing send button / suggested items pattern).
