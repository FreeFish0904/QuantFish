# Changes: Admin console

## Implemented

1. `frontend/src/features/admin/ui/AdminTabs.tsx` + `AdminTabs.module.css`: Moved `role="tablist"` to an inner `<div>` so the outer `<nav>` keeps its landmark, and removed `!important` from the active tab state by using the higher-specificity `.tab.active` selector.
2. `frontend/src/features/admin/view.tsx` + `cohortSubmissionsView.tsx`: Wrapped admin metadata in a `role="group"` container and moved the interactive Logout / back-link actions outside the labelled group.
3. `frontend/src/features/admin/ui/SubmissionsPanel.tsx`: Replaced the raw-error dialog's `aria-label` with `aria-labelledby` pointing to the visible `<h2 id="admin-raw-error-title">`.
4. `frontend/src/features/admin/ui/TeamsPanel.tsx` + `cohortSubmissionsView.tsx`: Styled "View submissions" and cohort back links with a new `.buttonLink` class that mirrors the shared Button hover/focus/active treatment.
5. `frontend/src/features/admin/ui/Panels.module.css`: Replaced the hardcoded `rgba(4, 12, 20, 0.5)` dialog backdrop with `var(--sf-overlay)`.
6. `frontend/src/features/admin/ui/Panels.module.css`: Replaced the inline `color-mix` violet soft surface with the existing `var(--sf-violet-soft)` token.
7. `frontend/src/features/admin/view.module.css`: Applied semantic soft surfaces (`--sf-emerald-soft` / `--sf-red-soft`) to dataset success/error toasts.
8. `frontend/src/features/admin/view.module.css`: Gated the dataset toast spinner and loading spinner animations behind `prefers-reduced-motion: no-preference`.
9. `frontend/src/features/admin/view.tsx` + `cohortSubmissionsView.tsx` + `view.module.css`: Added `role="status" aria-live="polite"` to loading containers, replaced the static loading icon with a spinning `LoaderCircle`, and added a fade-in entry animation to the dataset toast.
10. `frontend/src/features/admin/ui/Panels.module.css`: Removed the fixed `min-height: 78px` from `.field` and let gap/margin control rhythm.
11. `frontend/src/features/admin/ui/Panels.module.css`: Made `.table` `min-width: 100%` below `1120px`, restoring `1120px` only on wider viewports.
12. `frontend/src/features/admin/ui/MessagesPanel.tsx`: Replaced the plain empty-row message with the shared `<EmptyState title={t("admin.noMessages")} />` when no messages exist.
13. `frontend/src/features/admin/view.module.css` + `Panels.module.css`: Replaced hardcoded pixel font sizes (`12px`, `13px`, `16px`, `18px`, `20px`, `24px`) with existing typography tokens (`--sf-text-xs`, `--sf-text-sm`, `--sf-text-base`, `--sf-text-lg`, `--sf-text-xl`, `--sf-text-2xl`).
14. `frontend/src/features/admin/ui/Panels.module.css`: Added visible focus rings (`:focus-visible` / `:focus-within`) to admin inputs, selects, textareas, toggles, checkbox fields, cohort team options, and the password-reset toggle; added transitions for border/box-shadow/background.
15. `frontend/src/features/admin/ui/Panels.module.css`: Added a reduced-motion-gated fade/slide entry animation to the settings-history success toast.

## Skipped

- `#1` Standardize dialog backdrops in non-admin files (`submissions`, `history`, `SubmissionSourceDialog`) and global token edits — outside the admin console scope.
- `#2` Global `:focus-visible` baseline in `globals.css` / `Layout.module.css` — implemented admin-specific rings only; global baseline belongs to the theme/layout scope.
- `#3` Typography token additions to `tokens.css` and adoption in non-admin features — admin files already migrated to existing tokens; broader token work is out of scope.
- `#5` Complete soft accent surface token set and semantic aliases in `tokens.css` — only the admin violet usage was replaced with the existing `--sf-violet-soft` token.
- `#15` Shared Button `selected` variant — implemented the admin-side fix (removed `!important`); the shared Button change is not in this scope.
- `#103` Toast/loading exit transitions — exit animation would require delaying React unmount (functional behaviour change); only entry CSS animations and live-region semantics were added.

## Notes

- All changes are confined to `frontend/src/features/admin/**`.
- No React props, state, hooks, effects, routes, API calls, or i18n keys were changed.
- The shared `EmptyState`, `Button`, and `Link` components were used/styled but not modified.
- `cd frontend && npm run test -- --run` passed: 35 test files, 217 tests.
- `cd frontend && npm run build` passed.
