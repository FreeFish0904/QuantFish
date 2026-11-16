# Design Audit: App shell & routing

## Scope files
- `frontend/src/app/App.tsx`
- `frontend/src/routes.tsx`
- `frontend/src/main.tsx`

## Findings

### 1. Empty, error, and loading states: Route-level Suspense fallback is unstyled plain text
- **File:** `frontend/src/routes.tsx`
- **Lines:** `22-29` (fallback defined at line `25`)
- **Issue:** The fallback shown while lazy route chunks load is a bare `<div>` containing only translated text. It has no spinner, no centering within the shell's content area, no use of theme tokens for colour/typography/spacing, and no reduced-motion-aware animation. On route changes this creates a jarring, inconsistent loading experience.
- **Proposed change:** Replace the inline fallback with a styled loading placeholder: a centered flex container using `--space-*` and `--color-text-*` tokens, an `aria-hidden` animated spinner, and explicit `role="status"` / `aria-live="polite"`. Wrap the spinner animation with a `prefers-reduced-motion` media query so motion is disabled when requested. Keep the existing translated loading string as the accessible label. If the project already has a shared `Loading`/`Skeleton` primitive, use it here; otherwise centralise the fallback in a small `RouteLoading` component within the app-shell scope.
- **Risk:** low

### 2. Empty, error, and loading states: No styled error boundary for failed lazy routes
- **File:** `frontend/src/routes.tsx`
- **Lines:** `31-47`
- **Issue:** Lazy-loaded routes can fail to load (network error, code-splitting failure). The route tree has no `errorElement`, so React Router's default unstyled error UI may surface. Users are left without a consistent branded error state or a recovery affordance.
- **Proposed change:** Add a lightweight, design-token-styled `errorElement` to the route tree (e.g. on the root route or on each lazy route) that uses the shared `ErrorState` styling, displays a friendly message, and includes a "Retry" button. No functional route logic should change.
- **Risk:** medium

### 3. Accessibility: No programmatic focus target on route change
- **File:** `frontend/src/app/App.tsx`
- **Lines:** `5-10`
- **Issue:** `App.tsx` renders the route outlet inside `Shell` without a focusable content landmark. When users navigate, keyboard focus remains on the trigger (e.g. sidebar link), so screen-reader users may not be directed to the new page content.
- **Proposed change:** Wrap `<Outlet />` in a container with `tabIndex={-1}` (e.g. `<main>` or `<div role="main">`) and, on location change, move focus to that container. Provide a visible focus indicator only for keyboard navigation. If `Shell` already supplies the `<main>` landmark, move the focus target there instead.
- **Risk:** medium

### 4. Animation & motion: Route transitions are instantaneous
- **File:** `frontend/src/routes.tsx`
- **Lines:** `36-45`
- **Issue:** Route content swaps instantly with no transition. This can feel abrupt, especially when data is already cached and views appear to "snap" into place.
- **Proposed change:** Add a subtle cross-fade/slide-in transition inside `RouteElement` (or around `<Outlet />`) using CSS transitions and `prefers-reduced-motion`. Keep transition duration short (e.g. 150-200 ms) and do not delay rendering.
- **Risk:** low

## Summary
- Total findings: 4
- Low risk: 2
- Medium risk: 2
- High risk: 0
