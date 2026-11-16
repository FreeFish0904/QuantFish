# Changes: History

## Implemented
1. `frontend/src/features/history/view.module.css` (#70): Raw-error dialog backdrop switched from the hardcoded `rgba(4, 12, 20, 0.5)` to the theme token `--sf-overlay`; the `<pre>` block now uses `--sf-bg`, `--sf-text`, and `--sf-font-mono` to match the shared code-block surfaces, and the dialog gained `max-height` to mirror `SubmissionSourceDialog` body constraints.
2. `frontend/src/features/history/view.tsx` + `view.module.css` (#71): Promoted the page title from `<h2>` to `<h1>` (modal title remains `<h2>`) and updated the corresponding CSS selector.
3. `frontend/src/features/history/view.module.css` (#72): Reworked `.toolbar` into a responsive flex layout (`align-items: stretch`, `justify-content: flex-start`, `flex: 1 1 220px` per child) so wrapped controls align cleanly; below `640px` controls stack to full width.
4. `frontend/src/features/history/view.module.css` (#73): Changed `.errorText` colour from `--sf-text-muted` to `--sf-error` so error descriptions no longer visually recede.
5. `frontend/src/features/history/view.tsx` + `view.module.css` (#74): Replaced the inaccessible `title` tooltip on the disabled "My submissions only" toggle with persistent visible helper text using the existing `history.mySubmissionsLoginHint` copy, associated with the checkbox via `aria-describedby`.
6. `frontend/src/features/history/view.module.css` (#75): Replaced the hardcoded `.panel` gradient with the solid token `--sf-surface-strong`.
7. `frontend/src/features/history/view.module.css` (#76): Added explicit `::placeholder` styling to the search input using `--sf-text-muted` with `opacity: 1`.
8. `frontend/src/features/history/view.tsx` + `view.module.css` (#77): Added a mobile breakpoint to `.panelHeader` that stacks the title/subtitle and compare button vertically below `640px`, with the compare button expanding to full width.
9. `frontend/src/features/history/view.module.css` (#79): Removed the redundant `justify-content: space-between` from `.header` since it contains only one flex child.

## Skipped
- #69: Adding `aria-describedby` is safe, but the backlog item also requires functional behaviour changes (initial focus on the close button, Escape dismissal, and backdrop-click dismissal) that are outside the design-only scope.
- #78: The raw-error modal is mounted/unmounted by a conditional render, so a meaningful enter/exit transition requires animation state behaviour; a CSS-only transition would not run on mount/unmount and therefore was skipped as behaviour-dependent.
- #1, #2, #3, #14: These are cross-cutting or Shared UI primitive items (dialog backdrop standardization, global `:focus-visible`, typography tokens, loading-state primitive) not owned by History.

## Notes
- For #70, the raw error is still rendered in a native `<pre>` rather than swapped to `PythonCodeBlock`, because raw errors are not guaranteed to be Python source. The surfaces (backdrop, background, border, radius, padding, mono font) were aligned with the shared code-block/dialog conventions instead.
- No new i18n keys, props, hooks, effects, routes, or API calls were introduced.
- `cd frontend && npm run test -- --run` passes (217 tests).
- `cd frontend && npm run build` passes.
