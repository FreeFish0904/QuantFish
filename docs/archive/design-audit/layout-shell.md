# Design Audit: Layout shell

## Scope files
- `frontend/src/shared/layout/Shell.tsx`
- `frontend/src/shared/layout/Topbar.tsx`
- `frontend/src/shared/layout/Sidebar.tsx`
- `frontend/src/shared/layout/MobileNav.tsx`
- `frontend/src/shared/layout/NavButton.tsx`
- `frontend/src/shared/layout/useActiveNav.ts`
- `frontend/src/shared/layout/navConfig.ts`
- `frontend/src/shared/layout/Layout.module.css`
- `frontend/src/shared/layout/NavButton.module.css`

## Findings

### 1. Colour & surfaces: Shell background uses hard-coded gradient values
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `1–14`
- **Issue:** The `.shell` gradient lists literal hex colours (`#07111d`, `#111827`, `#0a1726`, `#e6f0f8`, etc.) instead of theme tokens. This makes the background inconsistent with the token-first surface system and harder to maintain across themes.
- **Proposed change:** Define shell-gradient tokens in `tokens.css` (e.g., `--sf-bg-gradient-start`, `--sf-bg-gradient-mid`, `--sf-bg-gradient-end`) and the radial-accent alpha token, then reference them in `.shell` and `:root[data-theme="light"] .shell`.
- **Risk:** medium

### 2. Spacing & alignment: Magic-number spacing throughout layout components
- **File:** `frontend/src/shared/layout/Layout.module.css`, `frontend/src/shared/layout/NavButton.module.css`
- **Lines:** `Layout.module.css:39,42,240,243`; `NavButton.module.css:10–11,47`
- **Issue:** Several spacing values (`10px`, `6px`, `2px`) are not drawn from the `--sf-space-*` scale, producing subtle inconsistencies between the sidebar, mobile nav, and nav buttons.
- **Proposed change:** Map these values to the token scale (e.g., `10px` → `var(--sf-space-2)` or `var(--sf-space-3)`, `6px` → `var(--sf-space-1)`/`var(--sf-space-2)`, `2px` → `var(--sf-space-0-5)` if added). If the design truly needs half-steps, add a `--sf-space-1-5` or `--sf-space-0-5` token.
- **Risk:** low

### 3. Interactive states: Topbar controls lack visible focus indicators
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `122–188`
- **Issue:** `.iconButton`, `.languageToggle`, `.loginLink`, and `.collapse` have no `:focus-visible` styles, relying on browser defaults. This is inconsistent with `.button` in `NavButton.module.css`, which receives the themed `--sf-focus-ring`.
- **Proposed change:** Extract a shared `.topbarControl:focus-visible` rule (or apply directly to each control) that sets `box-shadow: var(--sf-focus-ring); outline: none;` and verify contrast against the topbar backdrop.
- **Risk:** medium

### 4. Accessibility: `aria-label` on a generic `<div>` is not reliably exposed
- **File:** `frontend/src/shared/layout/Topbar.tsx`
- **Lines:** `47`
- **Issue:** The account status wrapper is a plain `<div className={styles.accountBox} aria-label={t("session.accountStatus")}>`. Without an explicit `role`, screen readers generally ignore `aria-label` on generic elements, so the account-status label is lost.
- **Proposed change:** Either add `role="status"` to the account box, or replace the wrapper with a `<section>`/`<span>` and include a visually hidden label, or move the status text into the visible flow so it is naturally announced.
- **Risk:** low

### 5. Interactive states: Disabled logout button has no visual disabled treatment
- **File:** `frontend/src/shared/layout/Layout.module.css`, `frontend/src/shared/layout/Topbar.tsx`
- **Lines:** `Layout.module.css:144–146`; `Topbar.tsx:59–68`
- **Issue:** When `logoutPending` is true, the logout button is `disabled` but only shows the global `cursor: not-allowed`. There is no opacity, colour, or background change to signal the disabled state.
- **Proposed change:** Add an `.iconButton:disabled` rule that lowers opacity (e.g., `opacity: 0.55`) and/or shifts the icon colour to `var(--sf-text-muted)`.
- **Risk:** low

### 6. Typography: Page title lacks explicit weight and heading scale
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `110–114`
- **Issue:** `.pageTitle` uses a one-off `font-size: 21px` and inherits normal weight, making the top-level page heading less visually dominant than the `font-weight: 700` eyebrow above it.
- **Proposed change:** Add heading tokens to `tokens.css` (e.g., `--sf-font-size-lg`, `--sf-font-weight-heading`) and set `.pageTitle` to a semibold/bold weight (`600` or `700`) with a line-height of at least `1.2`.
- **Risk:** low

### 7. Responsive layout: Touch targets in the topbar are smaller than recommended
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `122–188`
- **Issue:** `.iconButton` is `36px × 36px` and `.languageToggle` has `min-height: 36px`, which is below the WCAG 2.5.5 recommended minimum of `44 × 44` CSS pixels for touch targets.
- **Proposed change:** Increase `.iconButton` to `40px × 40px` (or `44px × 44px`) and raise the `.languageToggle` minimum height/touch area accordingly, while keeping the topbar visually balanced.
- **Risk:** low

### 8. Animation & motion: Sidebar collapse transition ignores reduced-motion preference
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `16–29`
- **Issue:** `.sidebar` animates `width` and `flex-basis` on collapse/expand, but there is no `@media (prefers-reduced-motion: reduce)` override. Users with vestibular or motion sensitivities must still see the animated resize.
- **Proposed change:** Add a reduced-motion block that sets `.sidebar { transition: none; }` when the user prefers reduced motion.
- **Risk:** low

### 9. Component consistency: Topbar interactive surfaces share styles through grouped selectors
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `122–135`
- **Issue:** `.livePill`, `.iconButton`, `.languageToggle`, and `.loginLink` are styled together in a single selector block. While visually aligned, this grouping makes it hard to vary states (hover/focus/disabled) per control and invites drift.
- **Proposed change:** Introduce a base `.topbarControl` class for the shared surface/border/radius/height rules and compose it onto each element, then add per-element modifiers for hover/focus states.
- **Risk:** low

### 10. Empty/error/loading states: Session-loading state is plain text
- **File:** `frontend/src/shared/layout/Topbar.tsx`
- **Lines:** `51–56`
- **Issue:** During `sessionLoading`, the account area renders `t("common.loading")` as normal bold text inside `.accountText`. The abrupt switch from text to team name can feel like a layout jerk and lacks affordance that data is being fetched.
- **Proposed change:** Show a small indeterminate spinner or a skeleton pill inside `.accountBox` while loading, keeping the surrounding layout stable.
- **Risk:** low

### 11. Responsive layout: Mobile nav horizontal scroll has no affordance
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `229–249`
- **Issue:** `.mobileNav` hides scrollbars and uses `overflow-x: auto`. With seven nav items, content may overflow the viewport, but there is no fade, peek, or paging indicator to signal that more items exist off-screen.
- **Proposed change:** Add a subtle edge fade via `mask-image` gradients, or ensure the last visible item is partially clipped to imply scrolling. Alternatively, distribute items more evenly on narrow viewports.
- **Risk:** low

### 12. Colour & surfaces: Topbar and mobile nav use different overlay tokens
- **File:** `frontend/src/shared/layout/Layout.module.css`
- **Lines:** `93`, `237`
- **Issue:** `.topbar` uses `--sf-overlay-light` while `.mobileNav` uses `--sf-overlay`. These are similar shell-level navigation surfaces but with different translucency, which can look unintentional.
- **Proposed change:** Standardise shell chrome on one surface token (e.g., `--sf-overlay`) or introduce a dedicated `--sf-chrome-surface` token for both topbar and mobile nav.
- **Risk:** low

### 13. Typography: Mobile nav label font sizes are very small
- **File:** `frontend/src/shared/layout/NavButton.module.css`
- **Lines:** `48`, `63`
- **Issue:** Mobile labels are `11px` and drop to `10px` below `360px`. At `10px`, text is difficult to read on high-density screens and below common minimum-size recommendations.
- **Proposed change:** Keep mobile labels at a minimum of `12px` across all breakpoints, using a typography token such as `--sf-font-size-xs` or `--sf-font-size-sm`.
- **Risk:** low

## Summary
- Total findings: 13
- Low risk: 12
- Medium risk: 1
- High risk: 0
