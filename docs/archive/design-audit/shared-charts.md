# Design Audit: Shared charts

## Scope files
- `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`
- `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`
- `frontend/src/shared/charts/ComposedChart/ComposedChart.test.tsx`
- `frontend/src/shared/charts/LineChart/LineChart.tsx`
- `frontend/src/shared/charts/LineChart/LineChart.module.css`
- `frontend/src/shared/charts/LineChart/LineChart.test.tsx`
- `frontend/src/shared/charts/MultiLineChart/MultiLineChart.tsx`
- `frontend/src/shared/charts/MultiLineChart/MultiLineChart.module.css`
- `frontend/src/shared/charts/MultiLineChart/MultiLineChart.test.tsx`
- `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.tsx`
- `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.module.css`
- `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.test.tsx`

## Findings

### 1. Colour & surfaces: Chart series colours are hardcoded hex literals
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`
- **Lines:** `8-14`
- **Issue:** Strategy, benchmark, alpha, drawdown, profit, loss, and axis fallback colours are defined as hardcoded hex constants (`#22d3ee`, `#fbbf24`, etc.). They do not reference theme tokens, so they will not adapt to light/dark theme switches or brand-token changes and create a maintenance burden.
- **Proposed change:** Map each semantic series colour to existing theme tokens (`--sf-cyan`, `--sf-amber`, `--sf-violet`, `--sf-red`, `--sf-emerald`) and introduce profit/loss semantic tokens (e.g., `--sf-profit`, `--sf-loss`) if the palette needs to differ from the base accent set.
- **Risk:** medium

### 2. Colour & surfaces: Tooltip surfaces are hardcoded for dark mode only
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`, `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.module.css`
- **Lines:** `121-135` (ComposedChart), `43-57` (LightweightSvgChart)
- **Issue:** Tooltip backgrounds (`rgba(7, 17, 29, 0.94)`), borders (`rgba(148, 163, 184, 0.22)`), text (`#e6edf7`), and date text (`#f8fafc`) are hardcoded. In light mode these will appear as a near-black box against a light page, breaking theme consistency.
- **Proposed change:** Replace tooltip background, border, and text colours with theme tokens (`--sf-overlay`, `--sf-overlay-light`, `--sf-border`, `--sf-text`, `--sf-text-muted`) so the tooltip adapts to `data-theme="light"`.
- **Risk:** medium

### 3. Colour & surfaces: SVG grid, axis, and label colours are hardcoded
- **File:** `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.module.css`
- **Lines:** `15-28`
- **Issue:** Grid lines (`rgba(148, 163, 184, 0.16)`), axis lines (`rgba(145, 164, 187, 0.52)`), and axis label fill (`#91a4bb`) use fixed slate values. They will not respond to theme changes and may become too faint or too strong in light mode.
- **Proposed change:** Define chart-specific semitransparent tokens derived from `--sf-text-muted` and `--sf-border` (e.g., `color-mix(in srgb, var(--sf-text-muted) 16%, transparent)`), and use them for grid, axis, and label fills.
- **Risk:** medium

### 4. Accessibility: Charts are not keyboard-explorable
- **File:** `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.tsx`
- **Lines:** `400-407`
- **Issue:** The SVG is marked `aria-hidden="true"` and `focusable="false"`, and tooltips only appear on `onPointerMove`. Keyboard and screen-reader users have no way to inspect individual data points or read the tooltip values.
- **Proposed change:** Expose the SVG to the accessibility tree when it has data, add `role="img"` with an `aria-label` describing the chart, and support keyboard navigation across data points (e.g., Left/Right arrows) to move focus and update the tooltip. Keep `focusable="false"` only on decorative elements, not the chart root.
- **Risk:** medium

### 5. Visual hierarchy: No visible chart title
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`, `frontend/src/shared/charts/LineChart/LineChart.tsx`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.tsx`
- **Lines:** `907` (ComposedChart), `37` (LineChart), `41` (MultiLineChart)
- **Issue:** The `title` prop is only exposed to assistive technologies via `aria-label` on `role="img"`. Sighted users must infer the chart subject from surrounding page context.
- **Proposed change:** Render the title as visible text above each chart (styled consistently with page headings) and associate it with the chart via `aria-labelledby`. Keep the existing `aria-label` as a fallback.
- **Risk:** low

### 6. Colour & surfaces: Profit/loss colours invert financial conventions
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`
- **Lines:** `12-13`
- **Issue:** `PROFIT_COLOR` is `#ef4444` (red) and `LOSS_COLOR` is `#22c55e` (green), which is the opposite of the usual red-loss/green-profit convention. This can confuse users, especially in a finance context, and is a barrier for colour-blind users who may rely on conventions.
- **Proposed change:** Swap profit to a green/emerald semantic token and loss to a red semantic token, or expose them as theme variables (`--sf-profit`, `--sf-loss`) with clear naming.
- **Risk:** medium

### 7. Accessibility: Legend does not communicate unavailable state beyond opacity
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`, `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`
- **Lines:** `913-934` (ComposedChart), `23-26` (CSS)
- **Issue:** Unavailable benchmark/alpha legend items are only distinguished by a reduced opacity (`0.62`). This is colour-only communication and may be missed by users with low vision or colour-vision deficiencies.
- **Proposed change:** Add a non-colour indicator such as a strikethrough, parentheses, or an "unavailable" icon, and include visually hidden text (or an `aria-label`) that explicitly says the series is unavailable.
- **Risk:** low

### 8. Component consistency: Legend styles are duplicated and divergent across chart types
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`, `frontend/src/shared/charts/LineChart/LineChart.module.css`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.module.css`
- **Lines:** `7-48` (ComposedChart), `7-28` (LineChart), `7-28` (MultiLineChart)
- **Issue:** `.legend`, `.legendItem`, and `.swatch` rules are repeated in three files with identical values. `ComposedChart` additionally introduces `.dotSwatch` and `.unitLabel`. Duplication makes future legend updates error-prone.
- **Proposed change:** Extract a shared `ChartLegend` component (or shared CSS module) used by `ComposedChart`, `LineChart`, and `MultiLineChart` so all legends share one source of truth.
- **Risk:** low

### 9. Responsive layout: X-axis labels have no overlap strategy
- **File:** `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.tsx`
- **Lines:** `436-443`
- **Issue:** X-axis labels are rendered at a fixed font size and always centered. On narrow viewports or with many points, labels can collide and become unreadable.
- **Proposed change:** Implement label collision detection, reduce font size at small widths, or rotate/skip labels based on available width and label count.
- **Risk:** low

### 10. Interactive states: Legend items have no hover/focus affordance
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`, `frontend/src/shared/charts/LineChart/LineChart.tsx`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.tsx`
- **Lines:** `537-554` (ComposedChart), `38-43` (LineChart), `42-48` (MultiLineChart)
- **Issue:** Legend items are static `<span>` elements with no hover, focus, or active states. Even if they remain non-interactive, they should not look identical to clickable controls; if interactivity is intended later, the current markup lacks keyboard support.
- **Proposed change:** If legends are decorative, keep them as spans but add a subtle hover highlight (`background`/`color` token transition). If they are intended to toggle series, convert them to `<button>` with focus rings and `aria-pressed` states.
- **Risk:** low

### 11. Animation & motion: No reduced-motion preference for animated scrolling
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`
- **Lines:** `589-602`, `665-716`
- **Issue:** Scroll-driven updates use `requestAnimationFrame` to throttle range recomputation. While not strictly an animation, the component does not query `prefers-reduced-motion` for any future motion additions and currently relies on smooth scroll behaviour.
- **Proposed change:** Honour `prefers-reduced-motion` by disabling any scroll-driven interpolation or smooth-scroll behaviour when the user prefers reduced motion, and document this in the component.
- **Risk:** low

### 12. Accessibility: Tooltip lacks `aria-describedby` association and escape dismissal
- **File:** `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.tsx`
- **Lines:** `519-531`
- **Issue:** The tooltip overlay is rendered as a `pointer-events: none` `div` containing `role="tooltip"`. It is not explicitly associated with the chart surface via `aria-describedby`, and keyboard users cannot dismiss it with `Escape`.
- **Proposed change:** Add an `id` to the tooltip, reference it from the chart surface with `aria-describedby` when active, and support `Escape` key dismissal when focus is inside the chart.
- **Risk:** low

### 13. Empty, error, and loading states: No loading skeleton or shimmer state
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`, `frontend/src/shared/charts/LineChart/LineChart.tsx`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.tsx`
- **Lines:** `777-779` (ComposedChart), `28-30` (LineChart), `32-34` (MultiLineChart)
- **Issue:** Components only handle the empty-data case (`points.length === 0`) and immediately render an `EmptyState`. There is no intermediate loading state, causing layout jumps while data is fetched.
- **Proposed change:** Add an optional `isLoading` prop that renders a chart-sized skeleton or pulsing placeholder using `--sf-surface`/`--sf-surface-strong` tokens, then transitions to the chart or empty state.
- **Risk:** low

### 14. Spacing & alignment: `LineChart` and `MultiLineChart` frames use `overflow: auto`
- **File:** `frontend/src/shared/charts/LineChart/LineChart.module.css`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.module.css`
- **Lines:** `30-35` (both files)
- **Issue:** The chart frame has `overflow: auto`, which can show scrollbars if content slightly exceeds bounds (e.g., due to sub-pixel SVG sizing). This is inconsistent with `ComposedChart`, which uses `overflow: hidden` for the non-scrollable frame.
- **Proposed change:** Use `overflow: hidden` unless intentional scrolling is required; if overflow is needed, restrict it to `overflow-x: auto` and set `overflow-y: hidden` to avoid vertical scrollbars.
- **Risk:** low

### 15. Colour & surfaces: Axis tick rule uses hardcoded colour
- **File:** `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`
- **Lines:** `115-119`
- **Issue:** `.axisTickRule` uses `rgba(145, 164, 187, 0.52)`, a hardcoded slate value. It will not adapt to theme changes and duplicates the axis-line colour used in `LightweightSvgChart.module.css`.
- **Proposed change:** Replace with a theme-derived value such as `color-mix(in srgb, var(--sf-text-muted) 52%, transparent)` or a dedicated `--sf-chart-axis` token.
- **Risk:** low

## Summary
- Total findings: 15
- Low risk: 11
- Medium risk: 4
- High risk: 0
