# Changes: Shared UI primitives

## Implemented

1. `frontend/src/shared/ui/Card/Card.module.css`: Added a default `.header h2` style (`1.125rem`, `font-weight: 700`, `line-height: 1.3`) so card titles sit visually below page headings without requiring consumer changes.
2. `frontend/src/shared/ui/Button/Button.module.css`: Added an `:active:not(:disabled)` pressed state (`translateY(1px)`) and raised disabled opacity from `0.48` to `0.6` for better readability.
3. `frontend/src/shared/ui/DataTable/DataTable.tsx`: Added `aria-selected={selectable ? selected : undefined}` to each data row in selectable mode.
4. `frontend/src/shared/ui/DataTable/DataTable.module.css`: Added subtle hover backgrounds for data rows and sort buttons, and ensured selected rows use `--sf-cyan-soft-hover` on hover. Replaced the mixed `10px var(--sf-space-3)` cell padding with `var(--sf-space-3)` on both axes.
5. `frontend/src/shared/ui/Badge/Badge.tsx`: Removed the generic `aria-label` that overrode visible text and added `role="status"` so the badge is exposed as a status region.
6. `frontend/src/shared/ui/Badge/Badge.test.tsx`: Updated brittle `getByLabelText` assertions to query by `role="status"` since the accessible name is now the visible label.
7. `frontend/src/shared/ui/EmptyState/EmptyState.tsx`: Added `role="status"` to the root container for live-region semantics.
8. `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.tsx`: Removed duplicate `aria-label={title}` from the dialog, added an `id` to the visible `<h2>`, and referenced it with `aria-labelledby`.
9. `frontend/src/shared/ui/PythonCodeBlock/PythonCodeBlock.module.css`: Replaced the hardcoded mono font stack with `font-family: var(--sf-font-mono);`.
10. `frontend/src/shared/submissions/ExecutionParametersTable.tsx`: Replaced the plain empty-state paragraph with the shared `<EmptyState>` component using the existing `executionParameters.unavailable` string.
11. `frontend/src/shared/submissions/ExecutionParametersTable.module.css`: Removed the now-unused `.unavailable` rule.

## Skipped

- **#14** Replace static `Info` `EmptyState` in loading flows: Requires adding a new `loading` prop or a new primitive and changes in multiple feature views outside this scope; would be a functional/contract change.
- **#15** Active/selected tab state without `!important`: Needs changes to `features/admin/ui/AdminTabs.module.css` and `features/leaderboard/view.module.css`, which are outside this scope.
- **#16** Align reimplemented `Card` surfaces to the shared `Card`: Requires switching feature panels (leaderboard, history) to use `<Card>`; those files are outside this scope.
- **#17** Shared link-as-button styling for Submissions and Session: Requires changes to feature views and their module CSS outside this scope.
- **#21** `EmptyState`/`ErrorState` heading-level prop: Adding a new `headingLevel` prop would change the component signature, which is disallowed for this design-only pass.
- **#1** (Shared UI primitive file, but owner is Theme & global tokens) Standardize dialog backdrop on `--sf-overlay`: Left for the theme scope because it depends on token decisions and also touches files outside this scope.

## Notes

- The typography-token work in backlog item **#3** was not applied because the required `--sf-text-*` tokens do not yet exist in `frontend/src/theme/tokens.css` and adding them is outside this scope.
- Two feature tests (`features/compare/view.test.tsx` and `features/submission-detail/view.test.tsx`) fail because chart legend text ("Strategy", "Group 1 (best)") is not rendered. These failures are unrelated to the shared UI primitive changes; no chart files were modified.
- To keep the suite green for changes owned by this scope, brittle `getByLabelText(/status: .../)` assertions in `features/dashboard/view.test.tsx` and `features/leaderboard/view.test.tsx` were updated to query by the visible badge text after the `Badge` `aria-label` was removed.
