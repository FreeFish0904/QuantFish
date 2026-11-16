# Design Audit: Shared UI primitives

## Scope files
- `frontend/src/shared/ui/Button/Button.tsx`
- `frontend/src/shared/ui/Button/Button.module.css`
- `frontend/src/shared/ui/Card/Card.tsx`
- `frontend/src/shared/ui/Card/Card.module.css`
- `frontend/src/shared/ui/Badge/Badge.tsx`
- `frontend/src/shared/ui/Badge/Badge.module.css`
- `frontend/src/shared/ui/DataTable/DataTable.tsx`
- `frontend/src/shared/ui/DataTable/DataTable.module.css`
- `frontend/src/shared/ui/EmptyState/EmptyState.tsx`
- `frontend/src/shared/ui/EmptyState/EmptyState.module.css`
- `frontend/src/shared/ui/ErrorState/ErrorState.tsx`
- `frontend/src/shared/ui/ErrorState/ErrorState.module.css`
- `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.tsx`
- `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.module.css`
- `frontend/src/shared/ui/PythonCodeBlock/PythonCodeBlock.tsx`
- `frontend/src/shared/ui/PythonCodeBlock/PythonCodeBlock.module.css`
- `frontend/src/shared/submissions/ExecutionParametersTable.tsx`
- `frontend/src/shared/submissions/ExecutionParametersTable.module.css`

## Findings

### 1. Colour & surfaces: Dialog backdrop uses a hardcoded colour that ignores light mode
- **File:** `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.module.css`
- **Lines:** `3`
- **Issue:** The backdrop background is hardcoded as `rgba(4, 12, 20, 0.5)`. The project already provides `--sf-overlay` and `--sf-overlay-light` tokens that adapt between dark and light themes, so the hardcoded value breaks theme consistency in light mode.
- **Proposed change:** Replace `background: rgba(4, 12, 20, 0.5);` with `background: var(--sf-overlay);` (or `--sf-overlay-light` if the intended shade is lighter).
- **Risk:** medium

### 2. Accessibility: Badge overrides visible text with an unreliable aria-label on a generic span
- **File:** `frontend/src/shared/ui/Badge/Badge.tsx`
- **Lines:** `59-64`
- **Issue:** The badge wraps an icon and visible label, but the root `<span>` also carries an `aria-label`. `aria-label` is not reliably supported on generic elements without an explicit role, and it overrides the visible text for screen readers that do honour it.
- **Proposed change:** Remove `aria-label` from the span (the visible label is already accessible) and optionally add `role="status"` to expose the badge as a status region. If a "Status:" prefix is required, render it as visually hidden text instead of an aria-label.
- **Risk:** medium

### 3. Accessibility: EmptyState lacks a status landmark
- **File:** `frontend/src/shared/ui/EmptyState/EmptyState.tsx`
- **Lines:** `12-22`
- **Issue:** EmptyState is rendered as a generic `<div>` with no role or live-region semantics, so assistive technologies may not surface it as an informational announcement when it appears dynamically.
- **Proposed change:** Add `role="status"` to the root `<div>`.
- **Risk:** low

### 4. Accessibility: DataTable selected rows do not expose aria-selected
- **File:** `frontend/src/shared/ui/DataTable/DataTable.tsx`
- **Lines:** `115-117`
- **Issue:** Rows can be selected and receive a visual `.selectedRow` background, but the `<tr>` does not declare `aria-selected`, so the selection state is only available through the checkbox.
- **Proposed change:** Add `aria-selected={selected}` to each data row when the table is in selectable mode.
- **Risk:** low

### 5. Component consistency: ExecutionParametersTable empty state does not use the EmptyState primitive
- **File:** `frontend/src/shared/submissions/ExecutionParametersTable.tsx`
- **Lines:** `14-16`
- **Issue:** When no execution parameters are available, the component renders a plain `<p>` with muted styling instead of the shared `EmptyState` component used for other empty-data scenarios.
- **Proposed change:** Replace the `<p>` with `<EmptyState title={t("executionParameters.unavailable")} />` (add a description prop if the i18n key exists) to keep empty-state visuals and spacing consistent.
- **Risk:** low

### 6. Interactive states: Button has no active/pressed visual feedback
- **File:** `frontend/src/shared/ui/Button/Button.module.css`
- **Lines:** `1-42`
- **Issue:** The button defines hover and focus-visible states but has no `:active` style, so users receive no tactile feedback during a mouse click or touch tap.
- **Proposed change:** Add an `:active:not(:disabled)` state, e.g. a slightly darker/lighter background or a 1px translate, using existing tokens.
- **Risk:** low

### 7. Interactive states: DataTable rows and sort buttons lack hover affordance
- **File:** `frontend/src/shared/ui/DataTable/DataTable.module.css`
- **Lines:** `22-44`, `50-67`
- **Issue:** Selectable rows and sortable column headers have no hover state, which reduces discoverability of their interactivity.
- **Proposed change:** Add a subtle hover background to rows (especially when selectable) and a hover colour or underline to `.sort` buttons.
- **Risk:** low

### 8. Typography: Hardcoded font sizes throughout primitives
- **File:** `frontend/src/shared/ui/Badge/Badge.module.css` line `6`; `frontend/src/shared/ui/DataTable/DataTable.module.css` lines `33`, `39`; `frontend/src/shared/ui/EmptyState/EmptyState.module.css` line `20`; `frontend/src/shared/ui/ErrorState/ErrorState.module.css` line `20`; `frontend/src/shared/ui/PythonCodeBlock/PythonCodeBlock.module.css` line `17`; `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.module.css` lines `34`, `40`
- **Issue:** Font sizes are hardcoded as `12px`, `13px`, `17px`, `0.875rem`, `1.05rem`, etc. without semantic typography tokens, making the type scale inconsistent and harder to maintain across the design system.
- **Proposed change:** Introduce semantic typography tokens (e.g. `--sf-text-xs`, `--sf-text-sm`, `--sf-text-base`, `--sf-text-lg`) in the theme and consume them in these primitives.
- **Risk:** low

### 9. Spacing & alignment: DataTable cell padding mixes token and arbitrary values
- **File:** `frontend/src/shared/ui/DataTable/DataTable.module.css`
- **Lines:** `25`
- **Issue:** Cell padding is declared as `10px var(--sf-space-3)`, mixing an arbitrary length with the spacing-token system.
- **Proposed change:** Use `var(--sf-space-3)` for both axes, or add a `--sf-space-2-5` (10px) token to the scale if 10px is intentional.
- **Risk:** low

### 10. Colour & surfaces: PythonCodeBlock uses a custom mono font stack instead of the theme token
- **File:** `frontend/src/shared/ui/PythonCodeBlock/PythonCodeBlock.module.css`
- **Lines:** `16`
- **Issue:** The code block hardcodes `"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace` instead of the project's `--sf-font-mono` token, which already encodes a consistent monospace stack.
- **Proposed change:** Replace the custom stack with `font-family: var(--sf-font-mono);`.
- **Risk:** low

### 11. Accessibility: SubmissionSourceDialog duplicates the title via aria-label
- **File:** `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.tsx`
- **Lines:** `30`, `32`
- **Issue:** The dialog has both `aria-label={title}` and a visible `<h2>{title}</h2>`, which can cause screen readers to announce the title twice.
- **Proposed change:** Remove `aria-label`, add an `id` to the `<h2>`, and reference it with `aria-labelledby` on the dialog.
- **Risk:** low

### 12. Component consistency: EmptyState and ErrorState lock heading level to h3
- **File:** `frontend/src/shared/ui/EmptyState/EmptyState.tsx` line `17`; `frontend/src/shared/ui/ErrorState/ErrorState.tsx` line `21`
- **Issue:** Both components always render an `<h3>`, which can skip heading levels or be semantically incorrect depending on where the component is placed in a page outline.
- **Proposed change:** Accept an optional `headingLevel` prop (defaulting to `h3`) so consumers can render `h1`/`h2`/`h4` as appropriate.
- **Risk:** low

### 13. Interactive states: Disabled Button relies only on low opacity
- **File:** `frontend/src/shared/ui/Button/Button.module.css`
- **Lines:** `22-25`
- **Issue:** Disabled buttons use `opacity: 0.48`, which makes labels appear faint and harder to read, and communicates disabled state purely through a transparency change.
- **Proposed change:** Pair the opacity reduction with a dedicated disabled surface/border colour (or raise opacity to at least `0.6`–`0.65`) while preserving clear visual distinction from enabled buttons.
- **Risk:** low

## Summary
- Total findings: 13
- Low risk: 11
- Medium risk: 2
- High risk: 0
