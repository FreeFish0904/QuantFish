# Cross-Cutting Consistency Review

## Checks performed
- Scanned all `frontend/src/**/*.module.css` and `frontend/src/**/*.tsx` for hardcoded colours (`#`, `rgb(`, `rgba(`) outside `theme/tokens.css`.
- Verified `:focus-visible` / `:focus-within` coverage for buttons, links, inputs, checkboxes/toggles, sort controls, and nav items.
- Checked `aria-live` usage on status regions and toasts.
- Confirmed reduced-motion guards for animations and transitions.
- Reviewed responsive breakpoints against the established set (`360px`, `560px`, `920px`).
- Replaced stray font-size / spacing magic numbers with existing `--sf-*` typography and spacing tokens where appropriate.
- Checked for undefined CSS custom properties and unused CSS artifacts.

## Changes made

### Tokens
1. `frontend/src/theme/tokens.css`: Added `--sf-backdrop` (light/dark variants) for dialog backdrops and `--sf-line-height-heading` to back the value used by `.pageTitle`.

### Hardcoded colours / undefined tokens
2. `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.module.css`: Replaced hardcoded `rgba(4, 12, 20, 0.5)` backdrop with `var(--sf-backdown)`.
3. `frontend/src/features/submissions/view.module.css`: Replaced hardcoded `rgba(4, 12, 20, 0.5)` backdrop with `var(--sf-backdrop)`.
4. `frontend/src/features/admin/ui/Panels.module.css`: Replaced undefined `var(--sf-danger)` with `var(--sf-error)`.

### Focus & accessibility
5. `frontend/src/features/admin/ui/ExecutionPanel.tsx`: Added `aria-live="polite"` and `aria-atomic="true"` to the stale-mark success toast (`role="status"`).
6. `frontend/src/features/history/view.module.css`: Added visible `:focus-visible` styles for `.link` / `.labelLink`.
7. `frontend/src/features/submissions/view.module.css`: Added visible `:focus-visible` style for `.linkButton`.

### Breakpoint consistency
8. `frontend/src/features/submissions/view.module.css`: `960px` → `920px`, `640px` → `560px`.
9. `frontend/src/features/history/view.module.css`: `640px` → `560px` (both occurrences).
10. `frontend/src/features/admin/view.module.css`: `900px` → `920px`.
11. `frontend/src/features/admin/ui/AdminTabs.module.css`: `900px` → `920px`.
12. `frontend/src/features/admin/ui/Panels.module.css`: `900px` → `920px`.
13. `frontend/src/features/dashboard/view.module.css`: `960px` → `920px`.
14. `frontend/src/features/session/view.module.css`: `768px` → `920px`.
17. `frontend/src/features/leaderboard/view.module.css`: `768px` → `920px`.
18. `frontend/src/features/compare/view.module.css`: `760px` → `920px`.
19. `frontend/src/features/submission-detail/view.module.css`: `640px` → `560px` (both occurrences).
20. `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`: `640px` → `560px`.

### Typography / spacing tokenization
21. `frontend/src/shared/ui/DataTable/DataTable.module.css`: `12px` → `--sf-text-xs`, `13px` → `--sf-text-sm`, `gap: 4px` → `--sf-space-1`.
22. `frontend/src/shared/ui/Card/Card.module.css`: `1.125rem` → `--sf-text-lg`, `line-height: 1.3` → `--sf-line-height-tight`.
23. `frontend/src/shared/ui/Badge/Badge.module.css`: `12px` → `--sf-text-xs`, `gap: 6px` → `--sf-space-1-5`.
24. `frontend/src/features/submission-detail/view.module.css`: `24px` → `--sf-text-2xl`, `16px` → `--sf-text-base`, `12px` labels → `--sf-text-xs`, `13px` meta → `--sf-text-sm`.
26. `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`: `1.125rem` → `--sf-text-lg`, `12px` → `--sf-text-xs`, `line-height: 1.2` → `--sf-line-height-tight`.
27. `frontend/src/shared/charts/LineChart/LineChart.module.css`: same tokenization as ComposedChart legend/title.
28. `frontend/src/shared/charts/MultiLineChart/MultiLineChart.module.css`: same tokenization as ComposedChart legend/title.
29. `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.module.css`: `12px` tooltip font → `--sf-text-xs`.
30. `frontend/src/features/history/view.module.css`: `1.5rem` → `--sf-text-2xl`, `0.875rem` → `--sf-text-sm`, `1rem` → `--sf-text-base`.
31. `frontend/src/features/submissions/view.module.css`: `1.5rem` → `--sf-text-2xl`, `0.875rem` → `--sf-text-sm`, `0.75rem` → `--sf-text-xs`, `1rem` → `--sf-text-base`.
32. `frontend/src/features/session/view.module.css`: `1.5rem` → `--sf-text-2xl`, `0.875rem` → `--sf-text-sm`.

### Clean-up
33. Deleted empty `frontend/src/shared/submissions/ExecutionParametersTable.module.css` left over after an earlier scope removed its only rule.

## Skipped / deferred
- `frontend/src/shared/charts/performanceGraphData.ts`: The 8-colour group palette remains hardcoded. Mapping it to theme tokens would require introducing a full chart palette token set, which is a larger design decision outside a pure consistency pass.
- Hardcoded hex values in chart test files (e.g., `ComposedChart.test.tsx`, `LineChart.test.tsx`) were left as test data; they do not affect the rendered UI theme.
- Touch targets: several buttons and link-as-button elements still use `min-height` of `36px`–`40px`. Bumping them all to `44px` would visibly shift layouts and should be scoped per feature.
- `frontend/src/features/admin/ui/Panels.module.css` keeps `@media (min-width: 1120px)` because it pairs with the admin table's `min-width: 1120px` and is necessary for wide tabular layouts.
- Some chart-rendering pixel metrics (e.g., `10px` gaps, `11px` axis labels, `132px`/`154px` min-widths, `8px` swatches) were left as layout-specific rendering values rather than spacing tokens.
- `EmptyState`/`ErrorState` headings keep a `17px` font size because the token scale has no matching step.

## Verification
- `npm run test -- --run`: **217 passed (35 test files)**
- `npm run build`: **passed**
