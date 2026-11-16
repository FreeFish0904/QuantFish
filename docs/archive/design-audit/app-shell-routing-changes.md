# Changes: App shell & routing

## Implemented
1. `frontend/src/routes.tsx`: Replaced the bare `<div>` Suspense fallback with a styled `RouteLoading` component. The new fallback centers a spinner and the existing `common.loading` text inside the content area, uses theme tokens for colour/spacing, adds `role="status"` and `aria-live="polite"`, and disables the spinner animation under `prefers-reduced-motion: reduce`.
2. `frontend/src/routes.tsx`: Added a styled `RouteError` component and attached it as `errorElement` on the root route and every lazy child route. It surfaces the shared `ErrorState` component (title from `common.error`, retry label from `common.retry`) and reloads the page on retry, keeping the shell visible for child-route failures.
3. `frontend/src/routes.module.css` (new): Contains the design-token styling for `RouteLoading` (centered placeholder, spinner keyframes, reduced-motion guard) and `RouteError` (centered wrapper).

## Skipped
- #118 Programmatic route focus target — deferred in the backlog; requires new routing focus-management behaviour (moving focus on location change) beyond pure visual polish.
- #119 Route transition animation — deferred in the backlog; adding cross-fade/slide transitions around `<Outlet />` is a non-trivial motion/performance change that should be evaluated after a performance baseline.

## Notes
- No i18n keys were added; both new components reuse existing `common.loading`, `common.error`, and `common.retry` strings.
- `RouteElement` no longer needs to call `useI18n` for the fallback text, but its public interface (`children`) is unchanged.
- Attaching `errorElement` to each child route keeps the `Shell` (sidebar, topbar, mobile nav) visible when a lazy view fails to load; the root `errorElement` provides a fallback for shell-level errors.
- All existing tests pass and `npm run build` succeeds.
