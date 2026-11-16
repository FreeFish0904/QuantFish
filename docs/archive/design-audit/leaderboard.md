# Design Audit: Leaderboard

## Scope files
- `frontend/src/features/leaderboard/view.tsx`
- `frontend/src/features/leaderboard/view.module.css`
- `frontend/src/features/leaderboard/view.test.tsx`
- `frontend/src/features/leaderboard/model.ts`
- `frontend/src/features/leaderboard/model.test.tsx`
- `frontend/src/features/leaderboard/api.ts`
- `frontend/src/features/leaderboard/formatting.ts`
- `frontend/src/features/leaderboard/index.ts`

## Findings

### 1. Empty, error, and loading states: Loading state uses the EmptyState component
- **File:** `frontend/src/features/leaderboard/view.tsx`
- **Lines:** `164-169`
- **Issue:** The loading state renders `<EmptyState>` with a static `Info` icon. EmptyState is semantically and visually intended for "no data" scenarios, not for in-progress loading. A loading state should use a spinner, skeleton, or progress indicator to communicate that data is being fetched.
- **Proposed change:** Replace the loading EmptyState with a dedicated loading pattern (e.g., a centered spinner or skeleton rows) and keep EmptyState for genuine empty results.
- **Risk:** medium

### 2. Accessibility: Metric tabs implement an incomplete ARIA tab pattern
- **File:** `frontend/src/features/leaderboard/view.tsx`
- **Lines:** `263-279`, `297`
- **Issue:** The metric switcher uses `role="tablist"`, `role="tab"`, and `aria-selected`, but the tabs lack `aria-controls` and the controlled table panel is a plain `<section>` rather than `role="tabpanel"`. Screen-reader users may not perceive the tab-to-panel relationship.
- **Proposed change:** Add `aria-controls` to each tab pointing to the panel id, convert the results section to `role="tabpanel"` with `aria-labelledby="leaderboard-table-title"`, and ensure focus moves into the panel on tab switch if appropriate.
- **Risk:** low

### 3. Spacing & alignment: Toolbar `space-between` can orphan the compare button on wrap
- **File:** `frontend/src/features/leaderboard/view.module.css`
- **Lines:** `27-33`
- **Issue:** `.toolbar` uses `justify-content: space-between` with `flex-wrap: wrap`. On medium or small viewports, the compare button can wrap to a new row and sit far to the right, visually detached from the search and filter controls.
- **Proposed change:** Use a grouped layout (e.g., left group for track/metric/search, right group for compare) with `margin-left: auto` for the compare group, or switch to a stacked layout at an intermediate breakpoint.
- **Risk:** low

### 4. Interactive states: Team entry links lack a focus-visible style
- **File:** `frontend/src/features/leaderboard/view.module.css`
- **Lines:** `162-173`
- **Issue:** `.entryLink` only defines a hover underline. There is no `:focus-visible` style, so keyboard navigation relies on the browser default outline, which may be subtle or inconsistent with the rest of the UI.
- **Proposed change:** Add a `:focus-visible` rule that mirrors the hover treatment (e.g., underline plus a token-based outline or color shift) using `--sf-focus-ring`.
- **Risk:** low

### 5. Component consistency: Active metric tab overrides Button hover/focus states with `!important`
- **File:** `frontend/src/features/leaderboard/view.module.css`
- **Lines:** `86-90`
- **Issue:** `.activeTab` uses `!important` on background, border, and color to override the ghost Button variant. This suppresses the base `Button.module.css` hover and focus transitions, making the active tab feel visually frozen and creating maintenance risk if Button tokens change.
- **Proposed change:** Refactor so the active tab state composes with the Button component (e.g., introduce a `selected` Button variant or use lower-specificity state classes) without `!important`.
- **Risk:** medium

### 6. Accessibility: Dynamic search/sort updates are not announced
- **File:** `frontend/src/features/leaderboard/view.tsx`
- **Lines:** `105-108`, `134-141`
- **Issue:** Typing in the search box or toggling column sort updates the table, but there is no `aria-live` region to announce the new result count or sort direction to assistive technologies.
- **Proposed change:** Add an off-screen or polite `aria-live` region near the table header that announces messages like "3 teams shown, sorted by Sharpe descending" when the dataset or sort changes.
- **Risk:** medium

### 7. Empty, error, and loading states: Empty state does not distinguish "no submissions" from "no search matches"
- **File:** `frontend/src/features/leaderboard/view.tsx`
- **Lines:** `319-324`
- **Issue:** Both an empty leaderboard and a search that returns zero results render the same `leaderboard.noRankedTitle` / `leaderboard.noRankedDescription` message. Users cannot tell whether the track has no ranked entries or whether their filter is too restrictive.
- **Proposed change:** Provide two EmptyState variants: one for the no-data case and one for the no-search-matches case, including a clear option to clear the search.
- **Risk:** low

### 8. Colour & surfaces: Normal leaderboard status maps to a warning "degraded" tone
- **File:** `frontend/src/features/leaderboard/view.tsx`
- **Lines:** `450-459`
- **Issue:** `leaderboardPageStatus` returns `status: "degraded"` (amber warning tone) with label `common.standby` whenever no rows are running and the stale condition is not met. A healthy, fully-scored leaderboard therefore displays a warning-colored badge, which visually implies a problem.
- **Proposed change:** Introduce a neutral or positive status for the healthy standby case (e.g., `status: "scored"` or a new "ready" status) and reserve `degraded`/`stale` for genuinely problematic states.
- **Risk:** medium

### 9. Visual hierarchy: Rank medal tiers are not visually differentiated
- **File:** `frontend/src/features/leaderboard/view.tsx`, `frontend/src/features/leaderboard/view.module.css`
- **Lines:** `360-371`, `155-160`
- **Issue:** Gold, silver, and bronze medals all render the same `Medal` icon with identical styling. The badge string is only exposed via `aria-label`; sighted users must infer medal tier from the rank number alone.
- **Proposed change:** Assign distinct colors or icons to medal tiers (e.g., gold/amber/red tints for the icon, or small tier labels) while keeping the rank number clear.
- **Risk:** low

### 10. Component consistency: Results panel reimplements the shared Card surface
- **File:** `frontend/src/features/leaderboard/view.module.css`
- **Lines:** `119-124`
- **Issue:** `.panel` duplicates the Card component's gradient background, border, radius, and shadow exactly. This creates duplication and risks visual drift if the Card surface is updated.
- **Proposed change:** Use the shared `<Card>` component for the results panel (with a custom body class to remove internal padding so the DataTable fills the panel) instead of redeclaring the surface styles.
- **Risk:** medium

### 11. Responsive layout: Only one narrow breakpoint leaves cramped intermediate widths
- **File:** `frontend/src/features/leaderboard/view.module.css`
- **Lines:** `175-189`
- **Issue:** The only responsive adjustment is at `max-width: 560px`. Between roughly 560px and 900px, the toolbar may still squeeze the tabs, search, and compare button into a single row with uneven gaps.
- **Proposed change:** Add an intermediate breakpoint (e.g., 768px or 880px) that stacks the toolbar into two rows or switches the metric tabs/search to full width earlier.
- **Risk:** low

### 12. Spacing & alignment: Pagination footer lacks visual separation from the results panel
- **File:** `frontend/src/features/leaderboard/view.module.css`
- **Lines:** `142-147`
- **Issue:** The pagination footer sits directly beneath the bordered panel with only the parent `gap` spacing. It has no background, border, or top padding, so it can visually blend into the panel edge.
- **Proposed change:** Add a subtle top border or background surface to the pagination bar, or inset it within the panel footer, to clarify its boundary.
- **Risk:** low

## Summary
- Total findings: 12
- Low risk: 8
- Medium risk: 4
- High risk: 0
