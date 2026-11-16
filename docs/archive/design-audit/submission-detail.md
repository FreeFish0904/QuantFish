# Design Audit: Submission detail

## Scope files
- `frontend/src/features/submission-detail/view.tsx`
- `frontend/src/features/submission-detail/view.module.css`
- `frontend/src/features/submission-detail/ui/KpiCard.tsx`
- `frontend/src/features/submission-detail/ui/KpiCard.module.css`
- `frontend/src/features/submission-detail/model.ts`
- `frontend/src/features/submission-detail/api.ts`
- `frontend/src/features/submission-detail/index.ts`
- `frontend/src/features/submission-detail/model.test.ts`
- `frontend/src/features/submission-detail/view.test.tsx`

## Findings

### 1. Typography: Hardcoded page and panel title sizes
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `18-24`, `51-54`
- **Issue:** `.title` is set to `font-size: 24px` and `.panelTitle` to `font-size: 16px`. The project uses rem-based sizing elsewhere (e.g., `1.5rem` in `features/submissions/view.module.css`) and has no dedicated typography tokens, but mixing px and rem across adjacent pages creates inconsistency and weakens the type scale.
- **Proposed change:** Convert title sizes to rem (`1.5rem` / `1rem` or matching the nearest token) and align with the submissions feature so the detail page feels like the same hierarchy. If a type scale is introduced later, these should reference it.
- **Risk:** low

### 2. Colour & surfaces: KPI "neutral" tone uses primary cyan accent
- **File:** `frontend/src/features/submission-detail/ui/KpiCard.module.css`
- **Lines:** `34-36`
- **Issue:** `.neutral` maps the KPI value colour to `--sf-cyan`, which is the platform's primary action/brand accent. This makes non-semantic KPIs visually compete with buttons and links and can imply an active/positive meaning where none exists.
- **Proposed change:** Use `--sf-text-muted` or a dedicated `--sf-text-secondary` token for neutral KPI values so that only semantic tones (positive/emerald, warning/amber, danger/red) draw attention.
- **Risk:** low

### 3. Accessibility: Toggle checkboxes lack consistent focus styling
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `80-95`
- **Issue:** The benchmark/alpha toggles are native checkboxes inside `.toggle` labels. They rely on the browser's default focus ring, which does not match the cyan `--sf-focus-ring` used by `Button`, `.input`, and `.trackOption` elsewhere in the product.
- **Proposed change:** Add a `.toggle input:focus-visible` selector that applies `box-shadow: var(--sf-focus-ring); outline: none;` (and optionally a rounded border) so keyboard users get the same focus affordance as other controls.
- **Risk:** low

### 4. Visual hierarchy: Stale and missing-series notices use muted text only
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `61-66`
- **Issue:** `.panelNotice` renders stale-result and missing-performance warnings in `--sf-text-muted` at 12px. Because the colour is identical to secondary metadata, these warnings do not read as alerts and may be skipped by users scanning the page.
- **Proposed change:** Introduce a semantic notice variant: use `--sf-amber` text on an `--sf-amber-soft` background with `--sf-amber-soft-border` for warning notices, keeping the existing muted style for purely informational hints. This matches the Badge warning tone already used for queued/running states.
- **Risk:** medium

### 5. Spacing & alignment: Panel header crams title, range controls, and toggles into one flex row
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `42-49`
- **Issue:** `.panelHeader` is a single `flex-wrap` row with `justify-content: space-between` and `align-items: center`. On narrow viewports the segmented range buttons and the two checkboxes wrap under the title without a clear grouping, causing uneven whitespace and making the controls feel attached to the heading rather than to the chart.
- **Proposed change:** Stack the header vertically on small screens (e.g., a `@media (max-width: 640px)` block) with the title/description on top and controls below left-aligned, or wrap the controls in their own sub-row with `gap: var(--sf-space-3)` so the title and toolbar remain visually distinct.
- **Risk:** medium

### 6. Responsive layout / Accessibility: Toggle controls fall below recommended touch target
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `80-95`
- **Issue:** `.toggle` sets `min-height: 34px` and the native checkbox is `16px × 16px`. This is smaller than the WCAG 2.5.5 recommended 44×44 CSS px target and can be difficult to tap accurately on mobile devices.
- **Proposed change:** Increase `.toggle` to at least `min-height: 44px` and enlarge the clickable label area (e.g., padding on the label or a custom styled checkbox) without reducing the visible compactness of the control. If the native checkbox remains small, ensure the entire label is the activation target.
- **Risk:** medium

### 7. Empty/loading states: Loading state uses an info icon
- **File:** `frontend/src/features/submission-detail/view.tsx`
- **Lines:** `142-148`
- **Issue:** The loading state reuses `EmptyState`, which hardcodes the `Info` icon. An info icon semantically signals "nothing to see" or "tip", not "data is being fetched", which can make the page feel unresponsive.
- **Proposed change:** Either add a `loading` variant to `EmptyState` (with a spinner or `LoaderCircle` icon) and use it here, or create a local `LoadingState` wrapper with a pulsing skeleton/placeholder so the loading affordance is consistent with the running-badge spinner used elsewhere.
- **Risk:** medium

### 8. Colour & surfaces: Hardcoded shadow remains in scoped CSS
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `110`
- **Issue:** `.groupMenu` declares `box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28)` directly. Although the related `groupSelector`/`groupButton` markup appears unused in `view.tsx`, the hardcoded value is a token violation and will break if the theme shadow is updated.
- **Proposed change:** Replace the raw shadow with `var(--sf-shadow)`. If the group menu is dead code, consider removing the related CSS entirely in a future cleanup pass.
- **Risk:** low

### 9. Responsive layout: Title and status badge can feel disconnected on mobile
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `9-16`
- **Issue:** `.header` uses `align-items: flex-start`, so the badge pins to the top of the title block. On small screens with a long submission label and metadata, the badge floats far from the visual centre of the header and the `flex-wrap` gap can leave the badge orphaned on its own line.
- **Proposed change:** On narrow viewports, stack the header vertically (`flex-direction: column; align-items: flex-start;`) and place the badge below the metadata so the title group and status read as a single block.
- **Risk:** low

### 10. Typography: Meta text size differs from adjacent feature
- **File:** `frontend/src/features/submission-detail/view.module.css`
- **Lines:** `26-29`
- **Issue:** `.meta` is `font-size: 13px`, while `features/submissions/view.module.css` uses `0.875rem` (14px) for muted helper text. The 1px difference is subtle but contributes to the detail page feeling visually "tighter" and less aligned with the submission flow.
- **Proposed change:** Align `.meta` and `.panelMeta` with the 14px/`0.875rem` pattern used in the submissions feature, or define a shared `--sf-text-sm` token and apply it consistently.
- **Risk:** low

### 11. Component consistency: KPI cards lack a subtle hover/press state
- **File:** `frontend/src/features/submission-detail/ui/KpiCard.tsx`
- **Lines:** `10-16`
- **Issue:** `KpiCard` renders a static `Card` with no transition. While the cards are not interactive in this scope, the design system would benefit from a consistent hover lift on cards. More importantly, the absence of any `title` or aria attribute means the value/label relationship is conveyed only by proximity.
- **Proposed change:** Add `aria-label={`${label}: ${value}`}` (or visually hidden text) to the card so screen-reader users hear the KPI as a single statement, and consider a `transition` on the Card component's transform/box-shadow for consistency with other surfaces.
- **Risk:** low

## Summary
- Total findings: 11
- Low risk: 8
- Medium risk: 3
- High risk: 0
