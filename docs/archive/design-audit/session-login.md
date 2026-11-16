# Design Audit: Session / login

## Scope files
- `frontend/src/features/session/view.tsx`
- `frontend/src/features/session/view.test.tsx`
- `frontend/src/features/session/view.module.css`
- `frontend/src/features/session/model.ts`
- `frontend/src/features/session/index.ts`
- `frontend/src/features/session/api.ts`

## Findings

### 1. Spacing & alignment / Component consistency: Inline error block is excessively tall
- **File:** `frontend/src/features/session/view.module.css`
- **Lines:** `94-96`
- **Issue:** The `.error` wrapper renders the shared `ErrorState` component, which is styled with `min-height: 190px` for full-page empty/error states. Inside the compact login card this creates a large, empty error block that dominates the form and wastes vertical space.
- **Proposed change:** Override the inline error container so it fits the card context: add `.error { min-height: auto; }` and reduce any excessive vertical padding. Alternatively, introduce a compact `ErrorState` variant (e.g., `size="compact"`) for inline card usage.
- **Risk:** medium

### 2. Component consistency / Interactive states / Accessibility: Submit-strategy link recreates Button styling but omits focus and active states
- **File:** `frontend/src/features/session/view.module.css`
- **Lines:** `79-92`
- **Issue:** `.submitLink` manually duplicates Button visual properties (soft cyan background, border, radius, font-weight, hover) but does not define `:focus-visible` or `:active` states, and uses a different `min-height` (38px) than the `Button` primitive (36px). Keyboard users receive no focus ring, and the component drifts from the shared Button contract.
- **Proposed change:** Add `:focus-visible { box-shadow: var(--sf-focus-ring); outline: none; }` and `:active { transform: translateY(1px); }` to `.submitLink`. Align `min-height` and padding with `Button.module.css` (36px / `0 var(--sf-space-3)`). Ideally, refactor the link to use the `Button` primitive with an `as`/`render` prop, but at minimum the design states should match.
- **Risk:** medium

### 3. Accessibility: Required form inputs lack `required` and `autoComplete` attributes
- **File:** `frontend/src/features/session/view.tsx`
- **Lines:** `57-74`
- **Issue:** Team name and password are functionally required (the submit button is disabled until both are filled), but the inputs have no `required` or `aria-required` attributes and no `autoComplete` hints. Screen-reader users may not perceive the required state, and password managers cannot reliably fill the fields.
- **Proposed change:** Add `required autoComplete="username"` to the team-name input and `required autoComplete="current-password"` to the password input.
- **Risk:** low

### 4. Interactive states / Animation & motion: Login button loading state has no spinner
- **File:** `frontend/src/features/session/view.tsx`
- **Lines:** `76-79`
- **Issue:** While `login.isPending` is true, the button label switches to "Logging in..." but there is no loading spinner or other motion cue to indicate an in-flight request.
- **Proposed change:** Render a spinning `Loader2` icon (e.g., from `lucide-react`) beside the label during the pending state, with `aria-hidden="true"`. Respect `prefers-reduced-motion` by using a static pending indicator or disabling the spin animation for users who request reduced motion.
- **Risk:** low

### 5. Visual hierarchy / Typography: Card title competes with page title
- **File:** `frontend/src/features/session/view.tsx`
- **Lines:** `41`
- **Issue:** The Card header uses a bare `<h2>`, which renders at the browser default `1.5rem`. This matches the explicitly styled page `<h1>` (`font-size: 1.5rem`), flattening the heading hierarchy and making the card title feel as prominent as the page title.
- **Proposed change:** Give the card header title a class (e.g., `styles.cardTitle`) and set `font-size: 1.125rem; font-weight: 700;` so it sits clearly below the page title.
- **Risk:** low

### 6. Interactive states / Animation & motion: Inputs lack hover feedback and transitions
- **File:** `frontend/src/features/session/view.module.css`
- **Lines:** `49-63`
- **Issue:** `.input` defines a `focus-visible` style but no `:hover` state and no CSS transition. Compared with the Button, which has both hover and transition effects, the input interaction feels abrupt and less polished.
- **Proposed change:** Add `.input:hover { border-color: var(--sf-border-strong); }` and `transition: border-color var(--sf-transition-fast), box-shadow var(--sf-transition-fast);` to `.input`.
- **Risk:** low

### 7. Responsive layout / Spacing & alignment: View padding is fixed across breakpoints
- **File:** `frontend/src/features/session/view.module.css`
- **Lines:** `1-6`
- **Issue:** `.view` uses `padding: var(--sf-space-4)` (16px) on all viewport sizes. On desktop widths the login form sits close to the viewport edges and feels cramped.
- **Proposed change:** Add a responsive step, e.g., `@media (min-width: 768px) { .view { padding: var(--sf-space-6); } }`, to give the form more breathing room on larger screens while keeping the tighter mobile padding.
- **Risk:** low

### 8. Colour & surfaces: Input background may read as detached from the card surface in light mode
- **File:** `frontend/src/features/session/view.module.css`
- **Lines:** `50`
- **Issue:** `.input` uses `--sf-bg` (the page background). In dark mode this creates clear contrast against the card surface, but in light mode the page background and card surface colours are close, which can make the input feel either detached or inconsistently placed on the card's gradient surface.
- **Proposed change:** Use `--sf-bg-elevated` for the input background so it reads as an elevated field that belongs inside the card in both themes.
- **Risk:** low

## Summary
- Total findings: 8
- Low risk: 6
- Medium risk: 2
- High risk: 0
