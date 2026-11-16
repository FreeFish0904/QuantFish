# Design Audit: Compare

## Scope files
- `frontend/src/features/compare/view.tsx`
- `frontend/src/features/compare/view.module.css`
- `frontend/src/features/compare/model.ts`
- `frontend/src/features/compare/api.ts`
- `frontend/src/features/compare/index.ts`
- `frontend/src/features/compare/view.test.tsx`
- `frontend/src/features/compare/model.test.ts`

## Findings

### 1. Colour & surfaces: Compare palette hardcoded outside theme tokens
- **File:** `frontend/src/features/compare/model.ts`
- **Lines:** `18`
- **Issue:** `COMPARE_COLORS` is defined as raw hex literals (`#22d3ee`, `#fbbf24`, `#34d399`, `#a78bfa`). These values happen to overlap with the semantic token palette, but they are not derived from `--sf-cyan`, `--sf-amber`, `--sf-emerald`, or `--sf-violet`. If the theme is adjusted or a light/dark variant changes a semantic colour, the compare charts and card accents will drift out of sync.
- **Proposed change:** Replace the hex array with references to the existing semantic tokens, e.g. by defining `COMPARE_COLORS` as `["var(--sf-cyan)", "var(--sf-amber)", "var(--sf-emerald)", "var(--sf-violet)"]`. If CSS custom properties cannot be consumed directly in the model, expose a small compare-colour token set in `theme/tokens.css` and reference it here.
- **Risk:** medium

### 2. Typography: Hardcoded pixel font sizes lack a consistent scale
- **File:** `frontend/src/features/compare/view.module.css`
- **Lines:** `16`, `24`, `31`, `54`, `60`, `85`, `90`, `119`, `125`, `137`, `163`, `179`, `217`
- **Issue:** Font sizes are scattered as arbitrary pixel values (`12px`, `13px`, `14px`, `15px`, `16px`, `22px`). This makes the compare view fragile to root font-size changes and misaligned with any future global type scale. In particular, `.executionParametersTitle` is `15px`, which sits awkwardly between the `16px` card/panel title and the `14px` body text.
- **Proposed change:** Consolidate sizes to a small set of rem-based or token-based steps (e.g., `0.75rem`, `0.875rem`, `1rem`, `1.375rem`). Align `.executionParametersTitle` with the `16px` title step used by `.cardTitle` and `.panelTitle`.
- **Risk:** low

### 3. Spacing & alignment: Detail toolbar bottom-aligns controls of different heights
- **File:** `frontend/src/features/compare/view.module.css`
- **Lines:** `166-172`
- **Issue:** `.detailToolbar` uses `align-items: flex-end`, forcing the small `12px` selector label and the taller segmented-button/checkbox controls onto their bottom edges. When the toolbar wraps, the misalignment between the label text and the button text is noticeable.
- **Proposed change:** Switch to `align-items: center` (or `baseline` if the label must align with button text) and let each control's internal padding establish vertical rhythm.
- **Risk:** low

### 4. Visual hierarchy: Panel header colour is set on the container then overridden
- **File:** `frontend/src/features/compare/view.module.css`
- **Lines:** `104-110`, `117-121`
- **Issue:** `.panelHeader` sets `color: var(--sf-cyan)`, but `.panelTitle` immediately overrides it with `color: var(--sf-text)`. Only the icon inherits the cyan tint. This creates a confusing CSS contract and makes the panel header's colour behaviour implicit.
- **Proposed change:** Remove `color: var(--sf-cyan)` from `.panelHeader`. Apply the cyan colour explicitly to the icon element, for example via a dedicated `.panelHeaderIcon` class, and keep `.panelTitle` as `var(--sf-text)`.
- **Risk:** low

### 5. Empty, error, and loading states: Loading states rendered as static EmptyState
- **File:** `frontend/src/features/compare/view.tsx`
- **Lines:** `183-189`, `327-333`
- **Issue:** Both the main compare loading state and the detailed-graph loading state use the static `EmptyState` component. There is no `aria-live` region, spinner, or reduced-motion-aware animation to communicate that data is actively loading.
- **Proposed change:** Introduce a dedicated loading placeholder (or extend `EmptyState` with a `loading` prop) that includes `role="status"` and `aria-live="polite"`, a small animated spinner, and a `prefers-reduced-motion` fallback to static text. Preserve the existing translated strings so tests that assert on loading text continue to pass.
- **Risk:** medium

### 6. Interactive states: Custom toggle lacks hover and focus affordance
- **File:** `frontend/src/features/compare/view.module.css`
- **Lines:** `129-146`
- **Issue:** `.toggle` styles the container but provides no `:hover`, `:focus-within`, or `:active` states beyond the native checkbox `accent-color`. Keyboard users may not see a visible focus indicator on the toggle as a whole.
- **Proposed change:** Add `:hover` (`background: var(--sf-slate-soft-hover)`), `:focus-within` (`box-shadow: var(--sf-focus-ring); outline: none`), and a transition for background/border-colour. Ensure the focus ring wraps the entire toggle, not just the native checkbox.
- **Risk:** low

### 7. Responsive layout: Card grid and KPI grid can overflow or cramp on narrow viewports
- **File:** `frontend/src/features/compare/view.module.css`
- **Lines:** `34-38`, `71-75`
- **Issue:** `.cardGrid` uses `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))`, which can force horizontal overflow on viewports narrower than roughly `280px` plus gaps and outer padding. `.kpiGrid` uses `repeat(3, 1fr)`, so each KPI cell can become very narrow on small cards.
- **Proposed change:** For `.cardGrid`, use `minmax(min(280px, 100%), 1fr)` so columns never exceed the available width. For `.kpiGrid`, add a narrow breakpoint (e.g., below `360px`) that stacks KPIs in a single column, or switch to `minmax(80px, 1fr)`.
- **Risk:** medium

### 8. Interactive states: Segmented-control touch targets are small
- **File:** `frontend/src/features/compare/view.module.css`
- **Lines:** `207-210`
- **Issue:** `.segmented button` sets `min-height: 32px`, which is below the recommended 44×44 CSS-pixel touch target for mobile/touch users.
- **Proposed change:** Increase `min-height` to at least `40px` (ideally `44px`) and add a matching `min-width`. Keep text vertically centred via the button's existing padding.
- **Risk:** low

### 9. Component consistency: Difference values lack visual trend treatment
- **File:** `frontend/src/features/compare/view.tsx`
- **Lines:** `436-456`
- **Issue:** The `diff` column in the KPI-differences table displays signed numbers with no colour or icon treatment. The `+`/`-` sign is preserved, but the column visually blends in with the other numeric columns, making positive/negative deltas harder to scan.
- **Proposed change:** Apply semantic colour classes to diff cells (positive → `--sf-emerald`, negative → `--sf-red`, zero → `--sf-text-muted`) while keeping the explicit sign so the meaning is not colour-only.
- **Risk:** low

### 10. Animation & motion: No transitions or reduced-motion support
- **File:** `frontend/src/features/compare/view.module.css`
- **Lines:** `129-146`, `185-198`, `200-210`
- **Issue:** Interactive elements (toggle, select, segmented buttons) have no transition for background, border, or box-shadow changes. There is also no `prefers-reduced-motion` guard for any compare-specific motion.
- **Proposed change:** Add `transition: background-color/border-color/box-shadow var(--sf-transition-fast)` to `.toggle`, `.detailSelector select`, and `.segmented button`. Wrap these transitions in `@media (prefers-reduced-motion: reduce) { transition: none; }`.
- **Risk:** low

### 11. Accessibility: Redundant aria-label on toggle
- **File:** `frontend/src/features/compare/view.tsx`
- **Lines:** `130-139`
- **Issue:** `DetailedGraphsToggle` wraps the checkbox in a `<label>` that already contains the visible toggle text, but the input also carries an identical `aria-label`. The visible label already provides the accessible name, so the `aria-label` is redundant.
- **Proposed change:** Remove `aria-label` from the checkbox and rely on the wrapping `<label>`. If the accessible name must differ from the visible text, use `aria-labelledby` pointing to the visible span.
- **Risk:** low

### 12. Colour & surfaces: Card accent colour has no fallback
- **File:** `frontend/src/features/compare/view.tsx`
- **Lines:** `99-102`
- **Issue:** `.cardAccent` receives `backgroundColor` directly from `submission.color` via inline style. If the value is empty or invalid, the accent bar disappears without a fallback.
- **Proposed change:** Set a default `background-color` on `.cardAccent` in the CSS module (e.g., `var(--sf-cyan)`) and allow the inline style to override it when a valid colour is present.
- **Risk:** low

## Summary
- Total findings: 12
- Low risk: 10
- Medium risk: 2
- High risk: 0
