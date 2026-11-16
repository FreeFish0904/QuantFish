# Changes: Dashboard

## Implemented
1. `frontend/src/features/dashboard/view.module.css`: Added KPI tone modifier classes (`.toneNeutral`, `.tonePositive`, `.toneWarning`, `.toneDanger`) and applied `font-variant-numeric: tabular-nums` to `.kpiValue`.
2. `frontend/src/features/dashboard/view.tsx`: Drove KPI value colour from the model's `tone` prop using the new tone modifier classes.
3. `frontend/src/features/dashboard/view.tsx` + `view.module.css`: Aligned latest submissions and live status surfaces by replacing the live status `<Card>` with a matching flat bordered `.panelSurface` wrapper.
4. `frontend/src/features/dashboard/view.module.css`: Simplified `.panelIntro` from a two-row grid to a flex column with `gap`, removing the empty second row.
5. `frontend/src/features/dashboard/view.tsx` + `view.module.css`: Added a `.subtitle` class to the course name with muted colour, single-line truncation, and a sensible `max-width`.
6. `frontend/src/features/dashboard/view.module.css`: Added a mobile breakpoint (`max-width: 560px`) that reduces `.view` padding from `--sf-space-5` to `--sf-space-4`.
7. `frontend/src/features/dashboard/view.tsx`: Removed `aria-labelledby` from the latest submissions `<section>` so the `DataTable` caption is no longer duplicated by the region landmark.
8. `frontend/src/features/dashboard/view.tsx` + `view.module.css`: Gave the live status `Activity` icon an explicit `.liveIcon` colour using `--sf-emerald` to reinforce liveness.

## Skipped
- #44 Unknown submission statuses currently fall back to `"offline"` (danger tone). A neutral tone would require a new `BadgeStatus` or `Badge` tone mapping in `frontend/src/shared/ui/Badge/Badge.tsx`, which is outside the Dashboard scope and would change a shared primitive.
- #14 The loading state uses the static `EmptyState` component. This item is owned by Shared UI primitives and requires extending `EmptyState` or adding a dedicated loading primitive in shared code; not implemented within Dashboard-only files.

## Notes
- All changes were confined to `frontend/src/features/dashboard/view.tsx` and `frontend/src/features/dashboard/view.module.css`.
- No React props, state, hooks, effects, routes, API calls, i18n keys, or shared primitives were modified.
- `cd frontend && npm run test -- --run` passed (217 tests).
- `cd frontend && npm run build` passed.
