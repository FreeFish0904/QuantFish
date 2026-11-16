# Changes: Shared charts

## Implemented

1. `shared/charts/ComposedChart/ComposedChart.tsx`: Mapped hardcoded series colors to theme CSS variables (`--sf-cyan`, `--sf-amber`, `--sf-violet`, `--sf-red`, `--sf-text-muted`). Added component-scoped `--sf-profit`/`--sf-loss` aliases that point to `--sf-emerald`/`--sf-red`, swapping the previous inverted red/green convention. Added a visible chart title element and `aria-labelledby` association on the `role="img"` container, keeping `aria-label` as a fallback.

2. `shared/charts/ComposedChart/ComposedChart.module.css`: Replaced hardcoded tooltip background/border/text colors with `--sf-overlay`, `--sf-border`, and `--sf-text`. Replaced hardcoded axis tick rule color with `color-mix(in srgb, var(--sf-text-muted) 52%, transparent)`. Added a `.chartTitle` style and `--sf-profit`/`--sf-loss` local tokens. Added hover background and transition to `.legendItem` and a non-colour `text-decoration: line-through` cue to `.legendUnavailable`.

3. `shared/charts/LightweightSvgChart/LightweightSvgChart.module.css`: Replaced hardcoded grid/axis/label/hover-rule colors with theme-derived values (`color-mix` on `--sf-text-muted`/`--sf-text`, and `var(--sf-text-muted)`). Replaced hardcoded tooltip background/border/text with `--sf-overlay`, `--sf-border`, and `--sf-text`.

4. `shared/charts/LineChart/LineChart.tsx`: Added a visible chart title element and `aria-labelledby` association on the `role="img"` container, keeping `aria-label` as a fallback.

5. `shared/charts/LineChart/LineChart.module.css`: Added `.chartTitle` style. Added hover background and transition to `.legendItem`. Changed `.frame` from `overflow: auto` to `overflow: hidden` to match `ComposedChart` and avoid sub-pixel scrollbars.

6. `shared/charts/MultiLineChart/MultiLineChart.tsx`: Added a visible chart title element and `aria-labelledby` association on the `role="img"` container, keeping `aria-label` as a fallback.

7. `shared/charts/MultiLineChart/MultiLineChart.module.css`: Added `.chartTitle` style. Added hover background and transition to `.legendItem`. Changed `.frame` from `overflow: auto` to `overflow: hidden` to match `ComposedChart` and avoid sub-pixel scrollbars.

8. `shared/charts/ComposedChart/ComposedChart.test.tsx`: Updated the brittle assertion that checked the literal tooltip date colour (`#f8fafc`) to verify it now uses the theme token `var(--sf-text)`.

## Skipped

- #32 Keyboard exploration and focus management for `LightweightSvgChart` — deferred in the backlog; requires new keyboard interaction behavior beyond pure visual polish.
- #35 Reduced-motion for scroll-driven updates — the current implementation does not use smooth-scroll or interpolation; adding reduced-motion guards would require introducing new behavior rather than polishing existing design.
- #36 Tooltip `aria-describedby` and Escape dismissal — `aria-describedby` requires stable unique IDs per chart instance, which would need a new hook or prop; Escape dismissal is new keyboard interaction behavior.
- #37 Loading skeleton state — requires adding a new `isLoading` prop to the chart components, which is a functional/API change outside this design-only pass.
- #39 X-axis label overlap strategy — deferred in the backlog; collision detection/rotation is a non-trivial layout change.

## Notes

- Chart titles are rendered as visible text above each chart and associated with the chart surface via `aria-labelledby`. Title IDs are derived from the chart title string to avoid adding new hooks; this assumes chart titles are unique within a page, which holds for current usage.
- The legend duplication part of #33 was partially addressed by adding consistent hover and unavailable-state styling to all three existing legend implementations. Extracting a shared component was avoided because it would introduce new files and imports beyond the design-only scope.
- Profit/loss semantics are implemented with component-scoped CSS variables (`--sf-profit`, `--sf-loss`) inside `.chart`, rather than global tokens, because the global token file is outside this scope.
- `npm run test -- --run` passed (217 tests across 35 files) and `npm run build` passed.
