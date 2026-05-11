# Frontend Changes: Dark/Light Mode Toggle Button

## Summary
Added a sun/moon theme toggle button to the bottom of the left sidebar that switches between the existing dark theme and a new light theme, with smooth animated transitions and localStorage persistence.

## Files Modified

### `frontend/index.html`
- Added an inline `<script>` in `<head>` that applies `light-theme` class to `<html>` immediately on load (prevents flash of wrong theme on page refresh).
- Added `div.sidebar-footer` at the bottom of `aside.sidebar` containing `button#themeToggle.theme-toggle` with two inline SVGs: `.icon-sun` (shown in dark mode) and `.icon-moon` (shown in light mode). Both SVGs have `aria-hidden="true"`; the button itself carries `aria-label="Toggle light/dark mode"`.

### `frontend/style.css`
- Added a second `*, *::before, *::after` rule with `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease` for smooth theme-switching across all elements.
- Added `html.light-theme { ... }` block that overrides all dark-theme CSS custom properties with light equivalents:
  - `--background: #f8fafc`, `--surface: #ffffff`, `--surface-hover: #e2e8f0`
  - `--text-primary: #0f172a`, `--text-secondary: #475569`
  - `--border-color: #cbd5e1`, `--assistant-message: #e2e8f0`
  - `--shadow: 0 4px 6px -1px rgba(0,0,0,0.1)`, `--welcome-bg: #eff6ff`
  - Primary/action blues are unchanged between themes.
- Added `display: flex; flex-direction: column` to `.sidebar` so `.sidebar-footer` can use `margin-top: auto` to stick to the bottom.
- Added `.sidebar-footer` styles: `margin-top: auto`, `padding-top: 1.25rem`, `border-top` separator.
- Added `.theme-toggle` button styles: 40×40px circle, no background, `--text-secondary` color, hover changes to `--primary-color` with a blue tint background. Focus ring via `focus-visible` matching the existing `--focus-ring` pattern.
- Added icon animation CSS: both `.icon-sun` and `.icon-moon` are `position: absolute` inside the button. In dark mode, moon is hidden (`opacity: 0; transform: rotate(-90deg) scale(0.8)`). In light mode (`html.light-theme`), sun hides and moon appears — each with a 0.3s opacity + transform transition creating a rotate-in effect.

### `frontend/script.js`
- Inside `setupEventListeners()`, added a click handler on `#themeToggle` that:
  - Toggles the `light-theme` class on `document.documentElement` (`<html>`).
  - Persists the preference to `localStorage` as `'light'` or `'dark'`.
- The initial theme application is handled by the inline head script (no JS delay/flash).

## Accessibility
- Button is a native `<button>` element — keyboard-navigable (Tab to focus, Enter/Space to activate) out of the box.
- `aria-label="Toggle light/dark mode"` provides screen-reader context.
- SVG icons have `aria-hidden="true"` so they are not read redundantly.
- Focus ring via `:focus-visible` (consistent with existing send button / suggested items pattern).
