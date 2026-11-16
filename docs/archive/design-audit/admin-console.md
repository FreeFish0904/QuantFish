# Design Audit: Admin console

## Scope files
- `frontend/src/features/admin/view.tsx`
- `frontend/src/features/admin/view.module.css`
- `frontend/src/features/admin/view.test.tsx`
- `frontend/src/features/admin/model.ts`
- `frontend/src/features/admin/model.test.ts`
- `frontend/src/features/admin/api.ts`
- `frontend/src/features/admin/index.ts`
- `frontend/src/features/admin/cohortSubmissionsView.tsx`
- `frontend/src/features/admin/cohortSubmissionsView.test.tsx`
- `frontend/src/features/admin/ui/AdminTabs.tsx`
- `frontend/src/features/admin/ui/AdminTabs.module.css`
- `frontend/src/features/admin/ui/OverviewPanel.tsx`
- `frontend/src/features/admin/ui/DatasetPanel.tsx`
- `frontend/src/features/admin/ui/ExecutionPanel.tsx`
- `frontend/src/features/admin/ui/TeamsPanel.tsx`
- `frontend/src/features/admin/ui/MessagesPanel.tsx`
- `frontend/src/features/admin/ui/SubmissionsPanel.tsx`
- `frontend/src/features/admin/ui/Panels.module.css`

## Findings

### 1. Accessibility: Status group wraps interactive controls with an unsemantic aria-label
- **File:** `frontend/src/features/admin/view.tsx`
- **Lines:** `229-236`
- **Issue:** The `.status` `<div>` has `aria-label` but no explicit `role`, so the label may be ignored by assistive technologies. It also contains the **Logout** `Button`, mixing metadata and an interactive control inside the same labelled group.
- **Proposed change:** Give the metadata wrapper an explicit `role="group"` and move the logout `Button` outside the group. Apply the same fix in `cohortSubmissionsView.tsx` for the back Link.
- **Risk:** low

### 2. Accessibility: `AdminTabs` `<nav>` loses its landmark to `role="tablist"`
- **File:** `frontend/src/features/admin/ui/AdminTabs.tsx`
- **Lines:** `46`
- **Issue:** The tab strip is wrapped in `<nav>` but immediately given `role="tablist"`, which overrides the navigation landmark. Users navigating by landmarks lose the "Admin sections" region.
- **Proposed change:** Keep `<nav aria-label="...">` for the landmark and move `role="tablist"` to an inner `<div>` that contains the tab buttons.
- **Risk:** low

### 3. Interactive states: Several admin inputs and toggles lack visible focus styles
- **File:** `frontend/src/features/admin/ui/Panels.module.css`
- **Lines:** `194-206`, `229-238`, `277-298`, `335-349`, `373-390`, `568-584`
- **Issue:** Team/cohort creation inputs, inline fields, message textarea, edit-stack inputs, password controls, and toggle/checkbox wrappers either share styling without a `:focus-visible` rule or rely solely on the native checkbox outline. This creates an uneven keyboard navigation experience across admin forms.
- **Proposed change:** Add `:focus-visible { box-shadow: var(--sf-focus-ring); outline: none; }` to all admin inputs, selects, textareas, and the password-reset toggle. Add `:has(input:focus-visible)` or `:focus-within` rings to `.toggle`, `.checkboxField`, and `.cohortTeamOption` so focus is visible on the styled container.
- **Risk:** medium

### 4. Accessibility: Raw-error dialog relies on `aria-label` instead of `aria-labelledby`
- **File:** `frontend/src/features/admin/ui/SubmissionsPanel.tsx`
- **Lines:** `391-397`
- **Issue:** The raw-error dialog uses `aria-label` for its accessible name while the visible `<h2>` title has no `id`. `aria-labelledby` is generally more robust and keeps the accessible name in sync with the visible heading.
- **Proposed change:** Add an `id` to the dialog `<h2>` and reference it with `aria-labelledby` on the dialog container.
- **Risk:** low

### 5. Component consistency: Plain anchor links sit among styled button actions
- **File:** `frontend/src/features/admin/ui/TeamsPanel.tsx`, `frontend/src/features/admin/cohortSubmissionsView.tsx`
- **Lines:** `519-524`, `145`
- **Issue:** The "view submissions" cohort link and the cohort-history back link are unstyled `<Link>` elements (default browser anchor styling), while adjacent actions use `Button variant="ghost"`. The mismatch in affordance, hover state, and focus ring is visually inconsistent.
- **Proposed change:** Render the links with a button-like link class or use the shared `Button` component (e.g., as a link) so they share the same hover, focus, and spacing treatment.
- **Risk:** low

### 6. Colour & surfaces: Dialog backdrop uses a hardcoded RGBA value
- **File:** `frontend/src/features/admin/ui/Panels.module.css`
- **Lines:** `394`
- **Issue:** `.dialogBackdrop` uses `rgba(4, 12, 20, 0.5)`, which is not a theme token and will not adapt if the dark/light palette changes.
- **Proposed change:** Introduce or reuse a backdrop token (for example `--sf-backdrop` derived from `--sf-bg` or `--sf-overlay` with opacity) and apply it here.
- **Risk:** low

### 7. Colour & surfaces: Violet team-group accent uses inline `color-mix` instead of a soft token
- **File:** `frontend/src/features/admin/ui/Panels.module.css`
- **Lines:** `510-513`
- **Issue:** All other team-group accents reference `--sf-*-soft` tokens, but `.teamGroupViolet` hard-codes `color-mix(in srgb, var(--sf-violet) 12%, transparent)`. This is inconsistent and harder to maintain.
- **Proposed change:** Add a `--sf-violet-soft` token to the theme and use it in `.teamGroupViolet`, matching the pattern used for cyan, emerald, amber, and red groups.
- **Risk:** medium

### 8. Visual hierarchy: Dataset toast background does not reflect semantic status
- **File:** `frontend/src/features/admin/view.module.css`
- **Lines:** `124-142`, `169-183`
- **Issue:** Success and error toast states only change the border and icon color; the background stays `--sf-surface`. The status change is therefore subtle and relies mostly on colour.
- **Proposed change:** Use semantic soft surfaces for the variants: `.datasetToastSuccess` background `--sf-emerald-soft` and `.datasetToastError` background `--sf-red-soft`.
- **Risk:** low

### 9. Animation & motion: Dataset toast spinner ignores reduced-motion preferences
- **File:** `frontend/src/features/admin/view.module.css`
- **Lines:** `191-199`
- **Issue:** `.datasetToastSpinner` always animates with an infinite rotation, with no `prefers-reduced-motion` guard.
- **Proposed change:** Wrap the spin keyframes and animation declaration inside `@media (prefers-reduced-motion: no-preference)`; for reduced motion, show a static processing icon.
- **Risk:** low

### 10. Animation & motion: Toast and loading states appear/disappear without transitions
- **File:** `frontend/src/features/admin/ui/Panels.module.css`, `frontend/src/features/admin/view.tsx`
- **Lines:** `625-651`, `139-146`
- **Issue:** The settings-history success `.toast` and the admin loading container mount/unmount instantly, and the loading indicator uses a static icon. There are no entry/exit transitions or reduced-motion handling.
- **Proposed change:** Add opacity/transform transitions to the toast and respect `prefers-reduced-motion`. For the loading state, use the platform spinner pattern with a polite live region (`role="status" aria-live="polite"`) and a reduced-motion fallback.
- **Risk:** low

### 11. Typography: Hardcoded font sizes lack a shared admin type scale
- **File:** `frontend/src/features/admin/view.module.css`, `frontend/src/features/admin/ui/Panels.module.css`
- **Lines:** `28-32`, `89-93`, `12-16`, `176-180`, `603-606`
- **Issue:** Title, login title, metric value, history section heading, and modal heading all use arbitrary pixel values (`24px`, `20px`, `16px`, `18px`). This makes the admin console hierarchy inconsistent and harder to keep in sync with the rest of the app.
- **Proposed change:** Introduce or adopt shared typography tokens (for example `--sf-text-xl`, `--sf-text-lg`, `--sf-text-base`) and apply them consistently across admin headings and data values.
- **Risk:** medium

### 12. Spacing & alignment: Form fields use a fixed min-height
- **File:** `frontend/src/features/admin/ui/Panels.module.css`
- **Lines:** `44`
- **Issue:** `.field` sets `min-height: 78px`, which can create uneven vertical rhythm when labels wrap or when validation/helper text is added.
- **Proposed change:** Remove the fixed `min-height` and rely on label/input spacing (`gap` and bottom margin) to keep fields aligned.
- **Risk:** low

### 13. Spacing & alignment / Responsive layout: Tables enforce a 1120 px min-width on mid-size viewports
- **File:** `frontend/src/features/admin/ui/Panels.module.css`
- **Lines:** `454-456`
- **Issue:** `.table` has `min-width: 1120px`, so on viewports between `900px` and `1120px` the table overflows horizontally inside `.tableWrap` even though the outer layout is not yet in mobile mode.
- **Proposed change:** Make `min-width` responsive (for example `min-width: 100%` below `1120px` and `1120px` above) or allow columns to wrap/narrow via a larger breakpoint.
- **Risk:** low

### 14. Empty, error, and loading states: Empty messages state is a plain table cell
- **File:** `frontend/src/features/admin/ui/MessagesPanel.tsx`
- **Lines:** `156-162`
- **Issue:** When there are no messages, the table renders a muted span inside a single row. This is inconsistent with other admin empty states that use the shared `EmptyState` component and feels visually underwhelming.
- **Proposed change:** Render the shared `EmptyState` above or below the table when `rows.length === 0`, or at least apply centered padded empty-row styling.
- **Risk:** low

### 15. Interactive states: Active tab uses `!important`, suppressing focus/hover states
- **File:** `frontend/src/features/admin/ui/AdminTabs.module.css`
- **Lines:** `19-23`
- **Issue:** `.active` overrides background, border, and text colour with `!important`, which can mask the button's own `:hover` and `:focus-visible` styles and makes selected+focused tabs harder to perceive.
- **Proposed change:** Replace `!important` with a more specific selector (for example `.tab.active`) so the selected state composes cleanly with focus and hover rings.
- **Risk:** low

## Summary
- Total findings: 15
- Low risk: 12
- Medium risk: 3
- High risk: 0
