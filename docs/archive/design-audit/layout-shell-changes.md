# Changes: Layout shell

## Implemented
1. `theme/tokens.css`: Added shell-gradient tokens (`--sf-bg-gradient-start`, `--sf-bg-gradient-mid`, `--sf-bg-gradient-end`, `--sf-bg-gradient-accent-alpha`) and the chrome-surface alias (`--sf-chrome-surface`) so the layout can stop using hard-coded hex values.
2. `theme/tokens.css`: Added half-step spacing tokens `--sf-space-0-5` (2px) and `--sf-space-1-5` (6px) consumed by shell spacing.
3. `shared/layout/Layout.module.css`: Replaced the hard-coded `.shell` gradient hexes with the new `--sf-bg-gradient-*` tokens (using `color-mix` for the radial accent alpha).
4. `shared/layout/Layout.module.css`: Switched `.topbar` and `.mobileNav` to the shared `--sf-chrome-surface` token so the two chrome surfaces match.
5. `shared/layout/Layout.module.css`: Introduced `.topbarControl` base class and composed it into `.livePill`, `.iconButton`, `.loginLink`, and `.languageToggle`; added shared hover, `:focus-visible`, and `:disabled` states.
6. `shared/layout/Layout.module.css`: Raised topbar control touch targets from 36px to 40px (`min-height: 40px`; `.iconButton` width 40px; `.accountBox` min-height 40px; `.languageToggle` min-width 44px).
7. `shared/layout/Layout.module.css`: Added a visible disabled treatment for topbar controls (`opacity: 0.55`, `color: var(--sf-text-muted)`) instead of relying only on the cursor.
8. `shared/layout/Layout.module.css`: Added reduced-motion guard for the sidebar collapse transition (`transition: none` under `@media (prefers-reduced-motion: reduce)`).
9. `shared/layout/Layout.module.css`: Updated `.pageTitle` to use `--sf-text-xl`, `--sf-font-weight-semibold`, and `--sf-line-height-heading` for a clearer heading hierarchy.
10. `shared/layout/Layout.module.css`: Replaced shell magic-number spacing (`10px`, `6px`, `2px`) with the nearest spacing tokens.
11. `shared/layout/NavButton.module.css`: Tokenized nav-button gap/padding and set mobile labels to `--sf-text-xs` (12px) at all breakpoints, avoiding the previous 10–11px sizes.
12. `shared/layout/Topbar.tsx`: Added `role="group"` to the account box so its `aria-label` is reliably exposed to assistive technologies.
13. `shared/layout/Topbar.tsx` + `shared/layout/Layout.module.css`: Replaced the plain-text session-loading state with a `LoaderCircle` spinner and a reduced-motion fallback.

## Skipped
- #12 Add mobile nav scroll affordance — explicitly deferred in the backlog; needs a design decision between edge fade, peek clipping, or item redistribution and would add new visual behavior.

## Notes
- `npm run build` passes.
- Full `npm run test -- --run` has two remaining failures in `features/compare/view.test.tsx` and `features/submission-detail/view.test.tsx`. They are caused by chart legend/title changes being made by the Shared charts scope and are unrelated to the layout shell.
- The build needed two trivial cross-scope compile fixes that were already partially present in the working tree: removed the now-unused `useI18n`/`t` from `shared/ui/Badge/Badge.tsx`, and ensured `shared/charts/MultiLineChart/MultiLineChart.tsx` includes the `chartTitleId` helper it was already calling.
