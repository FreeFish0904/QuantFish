# Changes: Submission detail

## Implemented
1. `frontend/src/features/submission-detail/ui/KpiCard.module.css`: Changed `.neutral` KPI value colour from `--sf-cyan` to `--sf-text-muted` so non-semantic KPIs no longer compete with actions (#62).
2. `frontend/src/features/submission-detail/view.module.css`: Added `.panelNoticeWarning` modifier using `--sf-amber` text on `--sf-amber-soft` with `--sf-amber-soft-border` for warning notices (#63).
3. `frontend/src/features/submission-detail/view.tsx`: Applied the `.panelNoticeWarning` modifier to both the stale-result notice and the missing-performance-series notice (#63).
4. `frontend/src/features/submission-detail/view.module.css`: Added a `@media (max-width: 640px)` breakpoint to `.panelHeader` that stacks the title block and controls vertically with left alignment (#64).
5. `frontend/src/features/submission-detail/view.module.css`: Increased `.toggle` min-height to `44px`, added horizontal padding, `cursor: pointer`, and a subtle hover background using `--sf-slate-soft-hover` to meet touch-target guidance (#65).
6. `frontend/src/features/submission-detail/view.module.css`: Replaced the hardcoded `.groupMenu` `box-shadow` with `var(--sf-shadow)` (#66).
7. `frontend/src/features/submission-detail/view.module.css`: Added a `@media (max-width: 640px)` breakpoint to `.header` that stacks the title/metadata and status badge vertically on narrow viewports (#67).

## Skipped
- #68 The KPI card accessible-name change requires the shared `Card` component to accept `aria-label` (or would require reimplementing Card styling locally). Shared UI primitives are outside this scope, so this is better handled by the Shared UI primitives owner.

## Notes
- All changes are confined to `frontend/src/features/submission-detail/`.
- No React props, state, hooks, effects, routes, API calls, i18n keys, or business logic were changed.
- The loading-state improvement (#14) is owned by Shared UI primitives and was therefore left out of this pass.
- `npm run test -- --run` passed: 217 tests across 35 files.
- `npm run build` passed.
