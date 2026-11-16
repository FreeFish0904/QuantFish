# Changes: Theme & global tokens

## Implemented
1. `theme/tokens.css`: Added typography scale tokens (`--sf-text-2xs` through `--sf-text-3xl`), line-height tokens (`--sf-line-height-tight/base/relaxed`), and weight tokens (`--sf-font-weight-normal/medium/semibold/bold`).
2. `theme/tokens.css`: Extended spacing scale with `--sf-space-7` (28px), `--sf-space-8` (32px), `--sf-space-10` (40px), `--sf-space-12` (48px), and `--sf-space-16` (64px).
3. `theme/tokens.css`: Added semantic color aliases `--sf-success`, `--sf-warning`, `--sf-error`, `--sf-info`, `--sf-profit`, and `--sf-loss`.
4. `theme/tokens.css`: Completed soft accent surface tokens (soft, soft-hover, soft-strong, soft-border) for emerald, amber, red, violet, and slate.
5. `theme/tokens.css`: Increased `--sf-focus-ring` opacity (dark: ~50%, light: ~45%) for stronger focus visibility.
6. `theme/tokens.css`: Added `prefers-color-scheme: light` media query so system light-mode preference is honored, and added `[data-theme="dark"]` for explicit dark override.
7. `theme/tokens.css`: Added `--sf-transition-none` and collapsed motion tokens to 1ms under `prefers-reduced-motion: reduce`.
8. `theme/tokens.css`: Added `forced-colors: active` adjustments for borders, focus rings, shadows, and overlays using system keywords.
9. `theme/globals.css`: Set `line-height: var(--sf-line-height-base)` on `body`.
10. `theme/globals.css`: Added global `:focus-visible` baseline for buttons, links, inputs, textareas, selects, and tabbable elements using `--sf-focus-ring`.
11. `theme/globals.css`: Added `.sr-only` and `.sr-only-focusable` screen-reader-only utility classes.
12. `theme/globals.css`: Added global reduced-motion safety net that suppresses unsolicited animations and transitions.
13. `theme/globals.css`: Added `forced-colors: active` safety net that removes decorative box-shadows and provides a system-color focus outline.

## Skipped
- #1 Requires replacing hardcoded backdrops in `features/admin/ui/Panels.module.css`, `features/submissions/view.module.css`, `features/history/view.module.css`, and `shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.module.css`, which are outside the Theme & global tokens scope.
- #6 Requires mapping chart/compare palette colors in `shared/charts/ComposedChart/ComposedChart.tsx` and `features/compare/model.ts`, which are outside the Theme & global tokens scope.

## Notes
- Token additions for typography (#3), soft accent/semantic colors (#5), and extended spacing (#7) are complete in `tokens.css`; adopting those tokens in consumer modules is pending the respective owner scopes.
- `npm run test -- --run` reports failures in Badge, chart, dashboard, compare, leaderboard, and submission-detail tests. These failures originate from changes in other scopes, not from the Theme & global token files.
- `npm run build` fails with `error TS6133: 'chartTitleId' is declared but its value is never read` in `src/shared/charts/MultiLineChart/MultiLineChart.tsx`, which is outside the Theme & global tokens scope.
