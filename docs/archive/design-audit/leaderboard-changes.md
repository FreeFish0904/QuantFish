# Changes: Leaderboard

## Implemented

1. `frontend/src/features/leaderboard/view.tsx`: **#80 Metric tabs ARIA** — added `id` to each metric tab, `aria-controls="leaderboard-panel"`, and converted the results `<section>` to `role="tabpanel"` with `aria-labelledby` pointing to the active metric tab.
2. `frontend/src/features/leaderboard/view.module.css`: **#81 Toolbar wrapping/orphan button** — grouped track selector, metric tabs, and search into `.toolbarMain`; moved the compare button into `.toolbarAction` with `margin-left: auto` so it does not detach on wrap.
3. `frontend/src/features/leaderboard/view.tsx`: **#82 Dynamic search/sort announcements** — added a polite, atomic `aria-live` region near the table that announces the visible row count and active sort header whenever the table re-renders.
4. `frontend/src/features/leaderboard/view.tsx`: **#83 Empty state distinction** — when the search input is non-empty and no rows match, the empty state now renders a clear-search action button (× icon with `aria-label={t("common.close")}`).
5. `frontend/src/features/leaderboard/view.tsx`: **#84 Healthy standby neutral badge tone** — changed the healthy-standby fallback in `leaderboardPageStatus` from `degraded` (amber warning) to `scored` (positive/emerald tone) while keeping the `common.standby` label.
6. `frontend/src/features/leaderboard/view.tsx` + `view.module.css`: **#85 Rank medal tier differentiation** — `RankCell` now applies `.gold`, `.silver`, or `.bronze` classes; medals render in amber, cyan, and red respectively while the rank number remains visible.
7. `frontend/src/features/leaderboard/view.module.css`: **#86 Responsive breakpoints** — added an intermediate `max-width: 768px` breakpoint that makes the compare button full-width, before the existing `560px` narrow breakpoint kicks in.
8. `frontend/src/features/leaderboard/view.module.css`: **#87 Pagination footer separation** — gave the pagination bar a subtle border, rounded corners, and a surface background so it no longer blends into the panel edge.
9. `frontend/src/features/leaderboard/view.tsx` + `view.module.css`: **Loading state visual** — replaced the loading `EmptyState` with a local centered spinner layout (`LoaderCircle` + reduced-motion guard) that preserves the existing loading title/description text.
10. `frontend/src/features/leaderboard/view.module.css`: **Active tab composes without `!important`** — removed `!important` from `.activeTab`, kept cyan-soft surfaces, and added a hover state so the selected metric tab no longer suppresses Button hover/focus transitions.
11. `frontend/src/features/leaderboard/view.module.css`: **Entry-link focus-visible** — added a token-based focus ring and underline to `.entryLink:focus-visible` for consistent keyboard navigation.

## Skipped

- **#14** Replace static `Info` `EmptyState` in loading flows with a shared loading pattern — owned by Shared UI primitives; requires editing `frontend/src/shared/ui/EmptyState/EmptyState.tsx`, which is outside the Leaderboard scope. Implemented a feature-local loading state instead.
- **#16** Align reimplemented `Card` surfaces to the shared `Card` component — would require a body-class prop on the shared `<Card>` or a fragile global selector to remove internal body padding; skipped to avoid drift and coupling.
- **#2** Add global `:focus-visible` baseline — owned by Theme & global tokens; out of scope. Added a local focus-visible style for leaderboard entry links instead.
- **#3** Introduce typography scale tokens and adopt rem sizing — owned by Theme & global tokens; out of scope.

## Notes

- `cd frontend && npm run test -- --run` passed: **217 tests** across 35 files.
- `cd frontend && npm run build` failed on a pre-existing, out-of-scope TypeScript error:
  ```
  src/features/admin/ui/MessagesPanel.tsx(6,1): error TS6133: 'EmptyState' is declared but its value is never read.
  ```
  This unused import is in the Admin console scope, not Leaderboard, so it was not modified.
