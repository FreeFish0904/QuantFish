# Design Audit: Submissions

## Scope files
- `frontend/src/features/submissions/view.tsx`
- `frontend/src/features/submissions/view.module.css`
- `frontend/src/features/submissions/view.test.tsx`
- `frontend/src/features/submissions/model.ts`
- `frontend/src/features/submissions/model.test.tsx`
- `frontend/src/features/submissions/api.ts`
- `frontend/src/features/submissions/test-setup.ts`
- `frontend/src/features/submissions/index.ts`

## Findings

### 1. Visual hierarchy / Typography: Card header titles compete with the page title
- **File:** `frontend/src/features/submissions/view.tsx`
- **Lines:** `142`, `258`
- **Issue:** Both `Card` headers render a bare `<h2>`, which uses the browser default `1.5rem`. The page `<h1>` is explicitly set to `1.5rem` in `view.module.css`, so the card titles appear equal in weight to the page title and flatten the heading hierarchy.
- **Proposed change:** Add a scoped class (e.g., `styles.cardTitle`) to each card header `<h2>` and set `font-size: 1.125rem; font-weight: 700;` so the cards read as subordinate to the page title.
- **Risk:** low

### 2. Colour & surfaces: Dialog backdrop uses a hardcoded dark overlay
- **File:** `frontend/src/features/submissions/view.module.css`
- **Lines:** `282-291`
- **Issue:** `.dialogBackdrop` uses `background: rgba(4, 12, 20, 0.5)` instead of a theme token. In light mode this still renders a dark overlay, and it will drift if the design-system overlay tokens are updated.
- **Proposed change:** Replace the hardcoded value with `--sf-overlay` or `--sf-overlay-light` from `theme/tokens.css`.
- **Risk:** low

### 3. Colour & surfaces: Environment download menu uses a custom shadow
- **File:** `frontend/src/features/submissions/view.module.css`
- **Lines:** `200-214`
- **Issue:** The `.menu` dropdown declares its own `box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28)` rather than reusing `--sf-shadow` or a dedicated menu-shadow token.
- **Proposed change:** Use `box-shadow: var(--sf-shadow)` (or introduce `--sf-shadow-menu`) so elevation remains consistent across surfaces.
- **Risk:** low

### 4. Interactive states / Accessibility: Download learning-data link lacks a visible focus indicator
- **File:** `frontend/src/features/submissions/view.module.css`
- **Lines:** `161-181`
- **Issue:** `.linkButton` is an anchor styled to look like a button. It defines hover and transition styles but has no `:focus-visible` rule, so keyboard users receive no focus ring.
- **Proposed change:** Add `.linkButton:focus-visible { box-shadow: var(--sf-focus-ring); outline: none; }` to match the shared `Button` primitive and other focusable controls in the form.
- **Risk:** medium

### 5. Component consistency: Download link recreates Button styling instead of reusing the primitive
- **File:** `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submissions/view.module.css`
- **Lines:** `220-227`, `161-181`
- **Issue:** The learning-data download is a custom `<a className={styles.linkButton}>` that duplicates the soft-cyan Button look. This duplicates CSS already owned by `shared/ui/Button/Button.module.css` and risks drift if the Button contract changes.
- **Proposed change:** If `Button` supports an `as`/`render` prop or a `href` variant, use it; otherwise create a small `LinkButton` primitive in `shared/ui` that shares the same styles and states.
- **Risk:** medium

### 6. Accessibility: Data-track selection state is communicated only by colour
- **File:** `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submissions/view.module.css`
- **Lines:** `188-208`, `116-144`
- **Issue:** The selected track option changes background from `--sf-surface` to `--sf-cyan-soft`, but there is no checkmark, border change, or other non-colour cue. Users with certain colour-vision deficiencies may have difficulty distinguishing the selected option.
- **Proposed change:** Add a `Check` icon or a left border accent to the selected option, or use `aria-pressed`/`aria-checked` styling that does not rely solely on background colour.
- **Risk:** medium

### 7. Animation & motion: Running-state icon is static
- **File:** `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submissions/view.module.css`
- **Lines:** `470`, `271-275`
- **Issue:** The `running` state renders a `LoaderCircle` icon, but no CSS animation is applied, so the "running" status receives the same motionless treatment as idle/queued/error.
- **Proposed change:** Add a slow spin keyframe (e.g., `@keyframes spin`) and apply it to the running icon with `@media (prefers-reduced-motion: no-preference)` so users who prefer reduced motion get a static indicator.
- **Risk:** low

### 8. Responsive layout: Environment download menu can overflow the viewport
- **File:** `frontend/src/features/submissions/view.module.css`
- **Lines:** `200-214`
- **Issue:** The menu is absolutely positioned with `left: 0` and `min-width: min(320px, calc(100vw - 32px))`. When the environment button wraps to a position away from the left edge, the right side of the menu can extend beyond the viewport before the min-width clamp takes effect.
- **Proposed change:** On narrow viewports, anchor the menu to the right of the button (`right: 0; left: auto;`) or make it full-width below the trigger; add a media query to keep the desktop left alignment when space is ample.
- **Risk:** low

### 9. Interactive states: Data-track options lack hover feedback
- **File:** `frontend/src/features/submissions/view.module.css`
- **Lines:** `116-144`
- **Issue:** `.trackOption` has a selected state but no hover state. The segment control therefore feels static and gives no pointer-affordance when the user hovers over an unselected option.
- **Proposed change:** Add `.trackOption:hover { background: var(--sf-slate-soft-hover); }` and a matching hover for the selected state so the control responds like other interactive surfaces.
- **Risk:** low

### 10. Empty/error/loading: Environment menu hints are unadorned text
- **File:** `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submissions/view.module.css`
- **Lines:** `330-336`, `221-225`
- **Issue:** Loading, error, and empty states inside the environment dropdown are rendered as plain `<span className={styles.menuHint}>`. They use the same muted text style with no icon or spinner, making them less scannable than the rest of the UI's empty/error states.
- **Proposed change:** Pair each hint with a small icon (`LoaderCircle` for loading, `AlertTriangle` for error, `PackageOpen` for empty) and keep the text styling compact.
- **Risk:** low

### 11. Accessibility: Selected filename is not announced to assistive technologies
- **File:** `frontend/src/features/submissions/view.tsx`
- **Lines:** `175-186`
- **Issue:** After a file is selected, the filename appears visually in a muted `<span>`, but there is no `aria-live` region, so screen-reader users may not be notified that their selection succeeded.
- **Proposed change:** Wrap the filename in `<span aria-live="polite" className={styles.muted}>{file.name}</span>` so the selection is announced without moving focus.
- **Risk:** low

## Summary
- Total findings: 11
- Low risk: 9
- Medium risk: 2
- High risk: 0
