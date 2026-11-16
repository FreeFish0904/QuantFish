# Design Audit: Dashboard

## Scope files
- `frontend/src/features/dashboard/view.tsx`
- `frontend/src/features/dashboard/model.ts`
- `frontend/src/features/dashboard/view.test.tsx`
- `frontend/src/features/dashboard/model.test.ts`
- `frontend/src/features/dashboard/view.module.css`
- `frontend/src/features/dashboard/index.ts`
- `frontend/src/features/dashboard/api.ts`

## Findings

### 1. Colour & surfaces: KPI values ignore the model's semantic tone
- **File:** `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/dashboard/view.module.css`
- **Lines:** `view.tsx:133-134`, `view.module.css:35-39`
- **Issue:** `toDashboardModel` assigns a `tone` to every KPI (`neutral`, `positive`, `warning`, `danger`), but `DashboardView` renders every value with the same `.kpiValue` class that hardcodes `color: var(--sf-cyan)`. This wastes the semantic signal and makes warning/danger KPIs (e.g., queued jobs, stale results) look identical to positive ones.
- **Proposed change:** Drive the KPI value colour from the model's `tone` prop by adding tone modifier classes (e.g., `tone-positive` → `--sf-emerald`, `tone-warning` → `--sf-amber`, `tone-danger` → `--sf-red`, `tone-neutral` → `--sf-cyan`) instead of a single cyan value.
- **Risk:** low

### 2. Empty, error, and loading states: Loading state uses the static EmptyState component
- **File:** `frontend/src/features/dashboard/view.tsx`
- **Lines:** `79-88`
- **Issue:** The loading state renders `<EmptyState>` with a static `Info` icon. EmptyState is visually and semantically intended for "no data" scenarios, not for in-progress loading. The icon does not communicate that data is being fetched, which can make the page feel frozen.
- **Proposed change:** Replace the loading EmptyState with a dedicated loading pattern (e.g., a centered `LoaderCircle` spinner or skeleton KPI cards) and reserve EmptyState for genuine empty results.
- **Risk:** medium

### 3. Spacing & alignment: `panelIntro` reserves an empty second row for the live status heading
- **File:** `frontend/src/features/dashboard/view.module.css`, `frontend/src/features/dashboard/view.tsx`
- **Lines:** `view.module.css:52-57`, `view.tsx:162-168`
- **Issue:** `.panelIntro` uses `grid-template-rows: auto minmax(1.25rem, auto)`. The live status panel has no description, so the second row is empty but still consumes at least `1.25rem` of vertical space. This creates uneven whitespace and throws off the vertical rhythm between the two columns.
- **Proposed change:** Simplify `.panelIntro` to a flex column layout (`display: flex; flex-direction: column; gap: var(--sf-space-2);`) and remove the fixed `minmax(1.25rem, auto)` row. Add a description element to the live status panel or leave the row absent.
- **Risk:** low

### 4. Component consistency: Latest submissions and live status use different surfaces
- **File:** `frontend/src/features/dashboard/view.tsx`
- **Lines:** `139-193`
- **Issue:** The latest submissions section relies on `DataTable`'s flat bordered wrapper, while the live status section sits inside the shared `<Card>` component with a gradient background and shadow. The two panels therefore have different visual weight and do not feel like part of the same dashboard.
- **Proposed change:** Align the surface treatment by wrapping the latest submissions `DataTable` in a `<Card>` (removing or overriding the DataTable's outer border if necessary) or by removing the Card from live status and using the same bordered wrapper style.
- **Risk:** medium

### 5. Typography / responsive layout: Course name paragraph has no truncation or styling
- **File:** `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/dashboard/view.module.css`
- **Lines:** `view.tsx:121-123`
- **Issue:** The course name is rendered in a plain `<p>` with no class, so it inherits body text styling and can wrap indefinitely. A very long class name could push the runner-status badge or make the header feel unbalanced.
- **Proposed change:** Add a `.subtitle` class with a muted colour, single-line truncation (`overflow: hidden; text-overflow: ellipsis; white-space: nowrap;`), and a sensible `max-width` so the header stays compact.
- **Risk:** low

### 6. Colour & surfaces / accessibility: Unknown submission statuses map to a danger tone
- **File:** `frontend/src/features/dashboard/view.tsx`
- **Lines:** `41-50`
- **Issue:** `badgeStatus` defaults any unknown status to `"offline"`, which renders with the danger tone (red). This visually implies a problem state for statuses that may simply be unrecognized, which is misleading and relies solely on colour to convey meaning.
- **Proposed change:** Map unknown statuses to an existing neutral tone (e.g., `"neutral"`) or introduce a dedicated `"unknown"` `BadgeStatus` that uses a muted/gray treatment, reserving red for genuinely failed/offline states.
- **Risk:** medium

### 7. Responsive layout: Dashboard view padding does not shrink on mobile
- **File:** `frontend/src/features/dashboard/view.module.css`
- **Lines:** `1-8`
- **Issue:** `.view` uses a fixed `padding: var(--sf-space-5)` (20px). The Shell already adds padding that shrinks on mobile, so the combined horizontal padding becomes 36px on small screens and feels excessive.
- **Proposed change:** Add a mobile breakpoint (e.g., `@media (max-width: 560px) { .view { padding: var(--sf-space-4); } }`) to reduce the inner padding and keep the layout breathable without wasting screen real estate.
- **Risk:** low

### 8. Accessibility: DataTable caption duplicates the section heading
- **File:** `frontend/src/features/dashboard/view.tsx`, `frontend/src/shared/ui/DataTable/DataTable.tsx`
- **Lines:** `view.tsx:140`, `view.tsx:147`, `DataTable.tsx:65-66`
- **Issue:** The latest submissions section has `aria-labelledby="latest-submissions-title"` and the inner `DataTable` has a `<caption>` with the exact same text. Screen-reader users are likely to hear the same label twice when navigating the table.
- **Proposed change:** Make the caption visually hidden but distinct (e.g., "Latest submissions table") or remove the section `aria-labelledby` and let the table caption serve as the accessible name for the region.
- **Risk:** low

### 9. Typography: KPI values do not use tabular numerals
- **File:** `frontend/src/features/dashboard/view.module.css`
- **Lines:** `35-39`
- **Issue:** `.kpiValue` displays large numeric counts without `font-variant-numeric: tabular-nums`. As values change, the glyph widths can shift slightly, making the dashboard feel less stable.
- **Proposed change:** Add `font-variant-numeric: tabular-nums;` to `.kpiValue` so digits align consistently across updates.
- **Risk:** low

### 10. Visual hierarchy: Live status Activity icon inherits body text colour
- **File:** `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/dashboard/view.module.css`
- **Lines:** `view.tsx:166`, `view.module.css:70-76`
- **Issue:** The `Activity` icon next to "Live status" is decorative and inherits the default heading colour. It misses an opportunity to reinforce the live/online state with the existing `--sf-emerald` token, making the panel heading feel visually flat.
- **Proposed change:** Give the Activity icon an explicit live colour class (e.g., `color: var(--sf-emerald)`) or wrap it in a small pulse indicator so the heading communicates liveness at a glance.
- **Risk:** low

## Summary
- Total findings: 10
- Low risk: 7
- Medium risk: 3
- High risk: 0
