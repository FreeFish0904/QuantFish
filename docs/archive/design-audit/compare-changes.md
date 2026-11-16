# Changes: Compare

## Implemented

1. `frontend/src/features/compare/model.ts`: Replaced raw hex literals in `COMPARE_COLORS` with semantic CSS custom properties (`var(--sf-cyan)`, `var(--sf-amber)`, `var(--sf-emerald)`, `var(--sf-violet)`) so the compare palette tracks theme tokens.
2. `frontend/src/features/compare/view.module.css`: Replaced hardcoded pixel font sizes with the existing typography scale tokens (`--sf-text-xs`, `--sf-text-sm`, `--sf-text-base`, `--sf-text-xl`) and swapped a few `2px` gaps/margins for `--sf-space-0-5`.
3. `frontend/src/features/compare/view.module.css`: Switched `.detailToolbar` from `align-items: flex-end` to `align-items: center` so controls of different heights align cleanly.
4. `frontend/src/features/compare/view.module.css` + `view.tsx`: Removed the container-level cyan colour from `.panelHeader` and applied it explicitly to the header icon via a new `.panelHeaderIcon` class.
5. `frontend/src/features/compare/view.module.css`: Added `:hover`, `:focus-within`, and `:active` states to `.toggle`, plus a transition for background/border/box-shadow; suppressed the inner checkbox focus ring so the whole toggle gets one focus ring.
6. `frontend/src/features/compare/view.module.css`: Made `.cardGrid` responsive with `minmax(min(280px, 100%), 1fr)` and stacked `.kpiGrid` to a single column below `360px`.
7. `frontend/src/features/compare/view.module.css`: Increased `.segmented button` touch target to `44px × 44px` (`min-height`/`min-width`).
8. `frontend/src/features/compare/view.tsx` + `view.module.css`: Added semantic colour classes for the KPI difference column (positive emerald, negative red, zero muted) while keeping the explicit sign.
9. `frontend/src/features/compare/view.module.css`: Added `transition` properties to `.toggle`, `.detailSelector select`, and `.segmented button`; motion is already gated globally via `prefers-reduced-motion`.
10. `frontend/src/features/compare/view.tsx`: Removed the redundant `aria-label` from the detailed-graphs toggle checkbox; the wrapping `<label>` already provides the accessible name.
11. `frontend/src/features/compare/view.module.css`: Added a default `background-color: var(--sf-cyan)` to `.cardAccent` so a missing inline colour falls back gracefully.
12. `frontend/src/features/compare/view.tsx` + `view.module.css`: Replaced static `EmptyState` loading placeholders with a local `CompareLoadingState` component that shows a spinner, `role="status"`, `aria-live="polite"`, and `aria-busy="true"`, while preserving the existing translated loading text.

## Skipped

- `#2` Add global `:focus-visible` baseline — requires editing `frontend/src/theme/globals.css`, which is outside the Compare scope.
- `#4` Respect `prefers-reduced-motion` in motion tokens and add a global safety net — requires editing global `tokens.css`/`globals.css`; Compare relies on the existing global reduced-motion rules.
- `#5` Complete soft accent surface tokens and semantic color aliases — owner Theme & global tokens / Admin, outside Compare scope.
- `#15` Active/selected tab state composes with `Button` without `!important` — owner Shared UI primitives / Leaderboard / Admin, outside Compare scope.
- `#16` Align reimplemented `Card` surfaces to the shared `Card` component — owner Shared UI primitives / Leaderboard / History / Mini-games, outside Compare scope.
- `#28`–`#39` Chart series/tooltip/legend/loading/overflow improvements — owner Shared charts, outside Compare scope.

## Notes

- Typography token adoption and the loading placeholder were implemented locally in Compare rather than as shared primitives, because editing files outside `frontend/src/features/compare/` was not allowed.
- The Compare palette change in `model.ts` keeps existing model tests passing because assertions reference `COMPARE_COLORS` rather than hardcoded hex values.
