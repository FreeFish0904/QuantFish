# Design Audit: History

## Scope files
- `frontend/src/features/history/view.tsx`
- `frontend/src/features/history/view.module.css`
- `frontend/src/features/history/model.ts`
- `frontend/src/features/history/api.ts`
- `frontend/src/features/history/view.test.tsx`
- `frontend/src/features/history/model.test.ts`
- `frontend/src/features/history/index.ts`

## Findings

### 1. Colour & surfaces: Modal backdrop uses hardcoded colour that breaks theme adaptation
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `134-143`
- **Issue:** `.dialogBackdrop` uses `background: rgba(4, 12, 20, 0.5)`, which is hardcoded and does not adapt to the light theme. In light mode this creates a dark overlay over an already-light surface, looking out of place and inconsistent with `SubmissionSourceDialog` (which uses the same hardcoded value, so both share the bug).
- **Proposed change:** Replace the hardcoded `rgba` with the existing theme token `--sf-overlay` or `--sf-overlay-light` so the overlay adapts with `data-theme="light"`.
- **Risk:** medium

### 2. Accessibility: Raw error modal lacks keyboard and screen-reader affordances
- **File:** `frontend/src/features/history/view.tsx`
- **Lines:** `597-625`
- **Issue:** The raw error dialog has `role="dialog"` and `aria-modal="true"` but provides no `aria-describedby` linking the error content, no focus trap, no initial focus on the close button, and no Escape or backdrop-click dismiss gesture. Keyboard and screen-reader users can open the modal but have no predictable way to leave it.
- **Proposed change:** Add `aria-describedby` pointing to the `<pre>` element, move initial focus to the close button, and add an `onKeyDown` Escape handler. Backdrop click-to-close can be provided by moving the backdrop click handler to the `.dialogBackdrop` element.
- **Risk:** medium

### 3. Component consistency: Raw error dialog duplicates shared dialog styling
- **File:** `frontend/src/features/history/view.tsx`, `frontend/src/features/history/view.module.css`
- **Lines:** `597-625`, `134-179`
- **Issue:** The raw error modal repeats backdrop, dialog container, header, and `<pre>` styling that already exists in `SubmissionSourceDialog`. Keeping two nearly identical dialog implementations invites visual drift (e.g., `max-width`, heading size, and backdrop already differ slightly).
- **Proposed change:** Extract a shared `Dialog` primitive with consistent backdrop, header, and body spacing, and render the raw error content inside it—mirroring how `SubmissionSourceDialog` is consumed.
- **Risk:** medium

### 4. Visual hierarchy: Page title and modal title share the same heading level
- **File:** `frontend/src/features/history/view.tsx`
- **Lines:** `476`, `606`
- **Issue:** Both the page title (`<h2 id="history-title">`) and the raw error modal title (`<h2>`) are `h2`. When the modal is open, the heading outline becomes flat and the modal title appears to be a sibling of the page title rather than a child overlay.
- **Proposed change:** Promote the page title to `<h1>` and keep the modal title as `<h2>`, or use `aria-level` to reflect the correct nesting without altering visual size.
- **Risk:** low

### 5. Responsive layout: Toolbar controls have a fixed min-width and uneven wrapping
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `27-47`
- **Issue:** `.toolbar` uses `justify-content: space-between` and every filter control (`search`, `statusFilter`, `accountToggle`) is locked to `min-width: 220px`. On narrow viewports the controls either overflow or wrap onto partial rows, producing ragged whitespace because `space-between` distributes a single wrapped item across the full width.
- **Proposed change:** Use a responsive grid or flex layout with `align-items: stretch`, reduce or remove `min-width` on small screens, and align wrapped rows to `flex-start` instead of `space-between`.
- **Risk:** low

### 6. Typography: Hardcoded font sizes are not anchored to a type scale
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `16-18`, `99-102`, `158-160`
- **Issue:** The page heading (`1.5rem`), panel heading (`1rem`), and dialog heading (`1.05rem`) are hardcoded. Because the project does not yet expose typography size tokens, History cannot align with a shared scale and may drift from other features as they evolve.
- **Proposed change:** Once type tokens are added to `theme/tokens.css` (e.g., `--sf-text-xl`, `--sf-text-lg`, `--sf-text-base`), replace the hardcoded rem values here. Until then, document the chosen scale in a comment so future changes stay intentional.
- **Risk:** low

### 7. Colour & surfaces: Error message text uses muted colour
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `120-126`
- **Issue:** `.errorText` is styled with `var(--sf-text-muted)`, making error messages visually recede. Since the error column also contains a warning icon button, the textual error description should share the warning/danger semantic.
- **Proposed change:** Use `--sf-red` (or a future `--sf-text-danger` token) for error text, or reduce the muted text to a secondary helper and lead with the warning-coloured icon/button.
- **Risk:** low

### 8. Interactive states: Submission links lack a visible focus style
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `105-118`
- **Issue:** `.labelLink` has a hover underline but no `:focus-visible` style. Keyboard users navigating the table rely on the browser default outline, which may be inconsistent with the custom focus ring used on buttons and filter controls.
- **Proposed change:** Add a `:focus-visible` rule that uses `box-shadow: var(--sf-focus-ring)` and a small `border-radius`, matching the focus treatment of `.search:focus-within` and `Button`.
- **Risk:** low

### 9. Empty, error, and loading states: Loading state uses a static info icon
- **File:** `frontend/src/features/history/view.tsx`
- **Lines:** `326-335`
- **Issue:** While loading, History renders `EmptyState`, which displays a static `Info` icon. At a glance this looks like an empty result rather than an in-progress load, and the component offers no loading motion.
- **Proposed change:** Use a dedicated loading indicator (e.g., a spinner or skeleton table) for the loading state, or add an animated loading icon inside `EmptyState` when used in a loading context.
- **Risk:** medium

### 10. Accessibility: Loading state is not announced to assistive technology
- **File:** `frontend/src/features/history/view.tsx`
- **Lines:** `326-335`
- **Issue:** The loading `<section>` has an `aria-label` but no `aria-live` region. Screen-reader users are not notified that the table is being fetched and may assume the page is silent/empty.
- **Proposed change:** Wrap the loading `EmptyState` in a container with `role="status"` and `aria-live="polite"`, or add an `aria-live="polite"` attribute to the section.
- **Risk:** low

### 11. Spacing & alignment: Header uses `justify-content: space-between` with a single child
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `9-14`
- **Issue:** `.header` declares `justify-content: space-between` but contains only one flex child (`<div>`). The declaration is redundant and suggests the layout is incomplete or copied from a template that expects an action button on the right.
- **Proposed change:** Remove `justify-content: space-between` or add a second child (e.g., a header-level action) and keep the alignment intentional.
- **Risk:** low

### 12. Interactive states: Disabled account toggle relies only on opacity and a title tooltip
- **File:** `frontend/src/features/history/view.tsx`, `frontend/src/features/history/view.module.css`
- **Lines:** `523-534`, `68-80`
- **Issue:** When the user is not logged in, the "My submissions only" checkbox is disabled and the hint is delivered via the `title` attribute. `title` is not accessible to keyboard or touch users, and the disabled state is communicated only through `opacity: 0.56`, which may not be enough for low-vision users.
- **Proposed change:** Render a persistent visible helper text (e.g., "Log in to filter by your team") next to or below the toggle, and use `aria-describedby` to associate it with the checkbox.
- **Risk:** low

### 13. Component consistency: Raw error block styling differs from source-code dialog
- **File:** `frontend/src/features/history/view.tsx`, `frontend/src/features/history/view.module.css`
- **Lines:** `616`, `163-172`
- **Issue:** Raw errors render in a plain `<pre>` with basic background/border styling, while source code uses `PythonCodeBlock` with labelled region, syntax highlighting, and consistent code-block surfaces. The two code-reading experiences feel visually unrelated.
- **Proposed change:** Render raw errors in a shared code-block primitive (or style the `<pre>` to match `PythonCodeBlock` surfaces) so both dialogs share padding, radius, and typography conventions.
- **Risk:** medium

### 14. Animation & motion: Raw error modal appears instantly
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `134-156`
- **Issue:** The dialog backdrop and container have no opacity or transform transition. The modal snaps in, which feels abrupt compared to the transition-based hover states used on buttons and filter controls.
- **Proposed change:** Add CSS transitions for opacity and a subtle translate-y on the dialog, gated by `@media (prefers-reduced-motion: no-preference)` to respect reduced-motion settings.
- **Risk:** low

### 15. Responsive layout: Panel header can stack awkwardly on narrow screens
- **File:** `frontend/src/features/history/view.tsx`, `frontend/src/features/history/view.module.css`
- **Lines:** `537-553`, `90-97`
- **Issue:** `.panelHeader` uses `align-items: flex-start` and `justify-content: space-between`. On narrow viewports the title/subtitle and the compare button can wrap onto separate rows, leaving the button dangling at the far edge while the title sits at the far left.
- **Proposed change:** Add a mobile breakpoint that switches `.panelHeader` to a column layout with `align-items: stretch` and full-width button, or keep the row but center-align items and use `flex-wrap: wrap`.
- **Risk:** low

### 16. Colour & surfaces: Panel uses a surface gradient not represented in tokens
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `82-88`
- **Issue:** `.panel` uses `background: linear-gradient(180deg, var(--sf-surface-strong), var(--sf-surface))`. The gradient is not captured as a token, so other panels in the app cannot easily match it and the surface treatment is harder to theme.
- **Proposed change:** Replace the gradient with a solid token (`--sf-surface` or `--sf-surface-strong`) or introduce a semantic token such as `--sf-panel-surface` that other features can reuse.
- **Risk:** low

### 17. Accessibility: Search placeholder colour is not styled
- **File:** `frontend/src/features/history/view.module.css`
- **Lines:** `56-66`
- **Issue:** The search input relies on the browser default placeholder colour, which may be too faint against the dark `var(--sf-surface)` background and can fail contrast requirements in some browsers.
- **Proposed change:** Add an explicit `::placeholder { color: var(--sf-text-muted); opacity: 1; }` rule for the search input.
- **Risk:** low

## Summary
- Total findings: 17
- Low risk: 13
- Medium risk: 4
- High risk: 0
