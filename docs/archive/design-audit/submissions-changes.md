# Changes: Submissions

## Implemented
1. `frontend/src/features/submissions/view.module.css`: Replaced the hardcoded `.menu` `box-shadow` with `var(--sf-shadow)` (#49).
2. `frontend/src/features/submissions/view.module.css`: Added a `@media (max-width: 640px)` rule that anchors the environment download menu to the right edge so it stays within the viewport on narrow screens (#52).
3. `frontend/src/features/submissions/view.module.css`: Added hover backgrounds for `.trackOption` and `.trackOption[data-selected="true"]` using existing soft tokens, plus a fast transition (#53).
4. `frontend/src/features/submissions/view.tsx` + `view.module.css`: Added a `Check` icon to each data-track option; the icon is hidden via CSS when the option is not selected, providing a non-colour selection cue (#50).
5. `frontend/src/features/submissions/view.module.css`: Added a `spin` keyframe and `.spinIcon` utility gated by `prefers-reduced-motion: no-preference`; applied the class to the running-state icon in `SubmissionStatePanel` (#51).
6. `frontend/src/features/submissions/view.tsx` + `view.module.css`: Added small icons (`LoaderCircle` with spin, `AlertTriangle`, `PackageOpen`) to the environment menu loading/error/empty hints and updated `.menuHint` to lay out icon + text compactly (#54).
7. `frontend/src/features/submissions/view.tsx`: Wrapped the selected filename in `<span aria-live="polite">` so the choice is announced to assistive technologies (#55).

## Skipped
- #1 Dialog backdrop tokenization — owner is Theme & global tokens; not Submissions-owned and would require editing a cross-cutting token file.
- #17 Shared link-as-button styling (`linkButton` focus/reuse) — owner is Shared UI primitives; requires changes to `shared/ui/Button` outside the Submissions scope.
- #18 Card header title hierarchy — owner is Shared UI primitives; requires changes to `shared/ui/Card` outside the Submissions scope.

## Notes
- All changes are confined to `frontend/src/features/submissions/view.tsx` and `frontend/src/features/submissions/view.module.css`.
- No React props, state, hooks, effects, routes, API calls, i18n keys, or business logic were changed.
- `npm run test -- --run` passes (217 tests) and `npm run build` passes.
