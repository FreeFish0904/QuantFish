# Design Audit: Theme & global tokens

## Scope files
- `frontend/src/theme/tokens.css`
- `frontend/src/theme/globals.css`

## Findings

### 1. Accessibility: Motion tokens ignore `prefers-reduced-motion`
- **File:** `frontend/src/theme/tokens.css`
- **Lines:** `60-63`
- **Issue:** The transition duration tokens (`--sf-transition-fast`, `--sf-transition-base`, `--sf-transition-slow`) are fixed values with no media-query override. Users who have requested reduced motion will still see 120–240 ms transitions everywhere those tokens are used.
- **Proposed change:** Add a `@media (prefers-reduced-motion: reduce)` block in `tokens.css` that collapses the transition tokens to `0ms` (or `1ms` to keep transition events firing). Optionally expose a `--sf-transition-none` token for component-level overrides.
- **Risk:** medium

### 2. Accessibility: Theme does not respect system color-scheme preference
- **File:** `frontend/src/theme/tokens.css`
- **Lines:** `1`, `70`
- **Issue:** `:root` hard-codes `color-scheme: dark`, and the light palette is only applied when `[data-theme="light"]` is present. A user whose OS is set to light mode will see a dark interface on first load unless the application explicitly sets the attribute.
- **Proposed change:** Add a `prefers-color-scheme: light` media query that mirrors the `[data-theme="light"]` block, so system preference is honored when no explicit theme attribute is set. Keep `[data-theme="light"]` and add `[data-theme="dark"]` for explicit overrides.
- **Risk:** medium

### 3. Typography: No type scale, line-height, or weight tokens
- **File:** `frontend/src/theme/tokens.css`
- **Lines:** `65-67`
- **Issue:** Only font-family tokens exist. Font sizes, line heights, and weights are not tokenized, so components will hardcode these values, leading to inconsistent headings, body copy, and chart labels.
- **Proposed change:** Add a type scale (e.g., `--sf-font-size-xs` through `--sf-font-size-3xl`), line-height tokens (`--sf-line-height-tight`, `--sf-line-height-base`, `--sf-line-height-relaxed`), and weight tokens (`--sf-font-weight-normal`, `--sf-font-weight-medium`, `--sf-font-weight-semibold`, `--sf-font-weight-bold`).
- **Risk:** medium

### 4. Interactive states: Missing global `:focus-visible` styles
- **File:** `frontend/src/theme/globals.css`
- **Lines:** `42-55`
- **Issue:** Interactive elements inherit browser-default focus rings, which vary by engine and may be low-contrast against the dark finance-cockpit palette. The existing `--sf-focus-ring` token is defined but never applied globally.
- **Proposed change:** Add a global `:focus-visible` rule using `--sf-focus-ring` for `button, a, input, textarea, select, [tabindex]:not([tabindex="-1"])`, and ensure components do not fully suppress outlines without providing an equivalent.
- **Risk:** medium

### 5. Colour & surfaces: Focus-ring opacity may be too subtle
- **File:** `frontend/src/theme/tokens.css`
- **Lines:** `44`, `93`
- **Issue:** `--sf-focus-ring` uses a 3 px shadow at only 22–26 % opacity. On elevated surfaces and in light mode the ring can be hard to perceive, risking WCAG 2.2 non-text contrast failures for focus indicators.
- **Proposed change:** Increase opacity to ~45–55 %, or switch to a dual-ring style (solid inner ring + translucent outer glow) while keeping the same token name.
- **Risk:** low

### 6. Spacing & alignment: Spacing scale stops at 24 px
- **File:** `frontend/src/theme/tokens.css`
- **Lines:** `46-52`
- **Issue:** The scale only covers `--sf-space-1` (4 px) through `--sf-space-6` (24 px). Page-level rhythm, sidebar widths, chart gutters, and section gaps often need 32–64 px, so authors will fall back to magic numbers.
- **Proposed change:** Extend the scale to at least `--sf-space-8: 32px`, `--sf-space-10: 40px`, and `--sf-space-12: 48px` (optionally `--sf-space-16: 64px`).
- **Risk:** low

### 7. Component consistency: Soft accent surface tokens are uneven
- **File:** `frontend/src/theme/tokens.css`
- **Lines:** `19-32`
- **Issue:** Cyan has soft, soft-hover, soft-strong, and soft-border variants; emerald has soft, border, and pulse; amber/red have only soft and border; slate has soft and soft-hover. This inconsistency makes it hard to build uniform hover, selected, and active states across all accent colors.
- **Proposed change:** Provide a consistent set for every accent (soft, soft-hover, soft-strong, soft-border) or document the intentional subset and recommended usage patterns.
- **Risk:** low

### 8. Accessibility: No screen-reader-only utility class
- **File:** `frontend/src/theme/globals.css`
- **Lines:** n/a (missing)
- **Issue:** There is no `.sr-only` / `.visually-hidden` utility class for text that should be exposed to assistive technology but hidden visually. Components will likely omit accessible labels or reimplement the pattern inconsistently.
- **Proposed change:** Add a standard `.sr-only` class with the clip pattern and a companion `.sr-only-focusable` variant for skip links.
- **Risk:** low

### 9. Typography: Base `line-height` is not defined
- **File:** `frontend/src/theme/globals.css`
- **Lines:** `19-27`
- **Issue:** The `body` rule sets `font-family` and smoothing but leaves `line-height` at the browser default (~1.2). Body text can feel cramped and will render differently across browsers.
- **Proposed change:** Add `line-height: 1.5;` to `body`, backed by a `--sf-line-height-base` token once it exists.
- **Risk:** low

### 10. Colour & surfaces: Missing semantic status color aliases
- **File:** `frontend/src/theme/tokens.css`
- **Lines:** `10-17`
- **Issue:** Semantic intent is tied directly to hue tokens (`--sf-emerald`, `--sf-amber`, `--sf-red`). There are no aliases such as `--sf-success`, `--sf-warning`, `--sf-error`, or `--sf-info`.
- **Proposed change:** Add semantic aliases mapping e.g. `--sf-success: var(--sf-emerald);`, `--sf-warning: var(--sf-amber);`, `--sf-error: var(--sf-red);`, `--sf-info: var(--sf-cyan);` so status colors can be updated independently of brand hues.
- **Risk:** low

### 11. Animation & motion: No global reduced-motion safety net
- **File:** `frontend/src/theme/globals.css`
- **Lines:** n/a (missing)
- **Issue:** Even if transition tokens are reduced, components may still define keyframe animations or one-off transitions. There is no global safety net to disable motion for users who prefer reduced motion.
- **Proposed change:** Add `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; } }` as a baseline.
- **Risk:** medium

### 12. Accessibility: No high-contrast / forced-colors support
- **File:** `frontend/src/theme/tokens.css`, `frontend/src/theme/globals.css`
- **Lines:** n/a (missing)
- **Issue:** There are no `forced-colors` or `prefers-contrast` adjustments. Subtle translucent borders (`rgba(..., 0.18)`), shadows, and overlays may disappear in Windows High Contrast Mode, breaking boundaries and status indicators.
- **Proposed change:** Add `forced-colors` media-query rules that use system keywords (`Canvas`, `CanvasText`, `Highlight`) for borders and focus rings, and remove decorative shadows when forced colors are active.
- **Risk:** low

## Summary
- Total findings: 12
- Low risk: 8
- Medium risk: 4
- High risk: 0
