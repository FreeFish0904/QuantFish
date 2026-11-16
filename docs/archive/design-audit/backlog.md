# Design-Polish Backlog

## Cross-cutting / theme / layout

- [ ] #1 Standardize hardcoded dialog backdrops on `--sf-overlay` — owner: Theme & global tokens — files: `frontend/src/features/admin/ui/Panels.module.css`, `frontend/src/features/submissions/view.module.css`, `frontend/src/features/history/view.module.css`, `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.module.css` — risk: medium
  - Issue: Several dialogs use the hardcoded `rgba(4, 12, 20, 0.5)` backdrop, which breaks theme adaptation (especially light mode) and duplicates maintenance.
  - Change: Replace each hardcoded value with the existing `--sf-overlay` token (or `--sf-overlay-light` where appropriate) so all backdrops respond to theme changes.

- [ ] #2 Add global `:focus-visible` baseline for interactive elements — owner: Theme & global tokens — files: `frontend/src/theme/globals.css`, `frontend/src/shared/layout/Layout.module.css`, `frontend/src/features/admin/ui/Panels.module.css`, `frontend/src/features/history/view.module.css`, `frontend/src/features/leaderboard/view.module.css`, `frontend/src/features/compare/view.module.css`, `frontend/src/features/session/view.module.css`, `frontend/src/features/submission-detail/view.module.css` — risk: medium
  - Issue: Browser-default focus rings vary across engines and many custom controls (topbar buttons, admin inputs, history links, compare toggles, session links, detail toggles) lack a visible themed focus indicator.
  - Change: Add a global `:focus-visible` rule in `globals.css` using `--sf-focus-ring` for buttons, links, inputs, textareas, selects and tabbable elements; remove per-component outline suppression that does not replace it.

- [ ] #3 Introduce typography scale tokens and adopt rem sizing — owner: Theme & global tokens — files: `frontend/src/theme/tokens.css`, `frontend/src/shared/ui/Badge/Badge.module.css`, `frontend/src/shared/ui/DataTable/DataTable.module.css`, `frontend/src/shared/ui/EmptyState/EmptyState.module.css`, `frontend/src/shared/ui/ErrorState/ErrorState.module.css`, `frontend/src/shared/ui/PythonCodeBlock/PythonCodeBlock.module.css`, `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.module.css`, `frontend/src/features/admin/view.module.css`, `frontend/src/features/admin/ui/Panels.module.css`, `frontend/src/features/compare/view.module.css`, `frontend/src/features/history/view.module.css`, `frontend/src/features/leaderboard/view.module.css`, `frontend/src/features/session/view.tsx`, `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submission-detail/view.module.css`, `frontend/src/shared/layout/NavButton.module.css` — risk: medium
  - Issue: Font sizes are hardcoded as `10px`, `11px`, `12px`, `13px`, `15px`, `16px`, `18px`, `20px`, `21px`, `24px` across primitives and features, producing an inconsistent hierarchy.
  - Change: Add `--sf-text-xs`, `--sf-text-sm`, `--sf-text-base`, `--sf-text-lg`, `--sf-text-xl` (plus line-height and weight tokens) and replace hardcoded sizes with the nearest token.

- [ ] #4 Respect `prefers-reduced-motion` in motion tokens and add a global safety net — owner: Theme & global tokens — files: `frontend/src/theme/tokens.css`, `frontend/src/theme/globals.css` — risk: medium
  - Issue: Transition duration tokens are fixed and there is no global reduced-motion fallback, so users who prefer reduced motion still see animations.
  - Change: Override `--sf-transition-*` to `0ms`/`1ms` inside `@media (prefers-reduced-motion: reduce)` and add a global safety net that suppresses unsolicited `animation`/`transition` durations.

- [ ] #5 Complete soft accent surface tokens and semantic color aliases — owner: Theme & global tokens — files: `frontend/src/theme/tokens.css`, `frontend/src/features/admin/ui/Panels.module.css` — risk: medium
  - Issue: Soft accent variants are uneven (cyan has hover/strong/border, emerald/amber/red/slate do not), and admin uses a one-off `color-mix` for violet because `--sf-violet-soft` is missing.
  - Change: Add a consistent soft/hover/strong/border set for every accent and semantic aliases (`--sf-success`, `--sf-warning`, `--sf-error`, `--sf-info`); replace admin's violet `color-mix` with `--sf-violet-soft`.

- [ ] #6 Replace hardcoded semantic color literals in charts and compare palette — owner: Theme & global tokens — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`, `frontend/src/features/compare/model.ts` — risk: medium
  - Issue: Chart series and compare palette use raw hex literals that happen to match the theme but will drift if tokens change.
  - Change: Map series/palette colors to existing semantic tokens (e.g., `--sf-cyan`, `--sf-amber`, `--sf-emerald`, `--sf-violet`) and introduce `--sf-profit`/`--sf-loss` aliases if needed.

- [ ] #7 Extend spacing scale and replace shell magic numbers — owner: Theme & global tokens — files: `frontend/src/theme/tokens.css`, `frontend/src/shared/layout/Layout.module.css`, `frontend/src/shared/layout/NavButton.module.css` — risk: low
  - Issue: Spacing stops at `24px` and shell uses one-off values (`2px`, `6px`, `10px`) outside the token scale.
  - Change: Extend tokens to `--sf-space-8`/`10`/`12`/`16` and map shell magic numbers to the nearest token.

- [ ] #8 Add screen-reader-only utility class — owner: Theme & global tokens — files: `frontend/src/theme/globals.css` — risk: low — deferred: no immediate consumer is blocked; add when the first component needs visually hidden helper text.
  - Issue: There is no standard `.sr-only` / `.visually-hidden` utility, so accessible labels are likely to be reimplemented inconsistently.
  - Change: Add `.sr-only` and `.sr-only-focusable` classes to `globals.css`.

- [ ] #9 Shell background gradient tokens — owner: Layout shell — files: `frontend/src/theme/tokens.css`, `frontend/src/shared/layout/Layout.module.css` — risk: medium
  - Issue: `.shell` hardcodes gradient hex values for dark and light modes, which breaks the token-first surface system.
  - Change: Define `--sf-bg-gradient-start`, `--sf-bg-gradient-mid`, `--sf-bg-gradient-end` and a radial-accent alpha token, then reference them in the shell gradient.

- [ ] #10 Unify topbar and mobile nav chrome surface token — owner: Layout shell — files: `frontend/src/theme/tokens.css`, `frontend/src/shared/layout/Layout.module.css` — risk: low
  - Issue: `.topbar` uses `--sf-overlay-light` while `.mobileNav` uses `--sf-overlay`, so similar chrome surfaces have different translucency.
  - Change: Introduce `--sf-chrome-surface` and apply it to both topbar and mobile nav.

- [ ] #11 Refactor topbar controls to a shared base class — owner: Layout shell — files: `frontend/src/shared/layout/Layout.module.css`, `frontend/src/shared/layout/Topbar.tsx` — risk: low
  - Issue: `.livePill`, `.iconButton`, `.languageToggle`, and `.loginLink` share a single grouped selector, making per-state styling fragile.
  - Change: Create a `.topbarControl` base class for shared surface/border/radius/height and compose modifiers for hover/focus/disabled.

- [ ] #12 Add mobile nav scroll affordance — owner: Layout shell — files: `frontend/src/shared/layout/Layout.module.css` — risk: low — deferred: needs a design decision between edge fade, peek clipping, or item redistribution; low impact.
  - Issue: `.mobileNav` hides scrollbars with `overflow-x: auto`; seven nav items can overflow without any visual cue.
  - Change: Add a subtle edge fade (`mask-image` gradient) or clip the last visible item to imply scrolling.

- [ ] #13 Page title weight and heading scale — owner: Layout shell — files: `frontend/src/theme/tokens.css`, `frontend/src/shared/layout/Layout.module.css` — risk: low
  - Issue: `.pageTitle` uses an arbitrary `21px` size and inherits normal weight, so the top-level heading is less dominant than the eyebrow.
  - Change: Apply a heading token (`--sf-text-xl`) and `font-weight: 600/700` with a `line-height >= 1.2`.

## Shared UI primitives / charts

- [ ] #14 Replace static `Info` `EmptyState` in loading flows with a shared loading pattern — owner: Shared UI primitives — files: `frontend/src/shared/ui/EmptyState/EmptyState.tsx`, `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/history/view.tsx`, `frontend/src/features/leaderboard/view.tsx`, `frontend/src/features/compare/view.tsx`, `frontend/src/features/submission-detail/view.tsx`, `frontend/src/app/routes.tsx` — risk: medium
  - Issue: Loading states render `EmptyState` with a static `Info` icon, which looks like an empty result rather than an in-progress load.
  - Change: Extend `EmptyState` with a `loading` prop (spinner + polite live region, reduced-motion fallback) or add a dedicated `LoadingState` primitive, and use it for all loading flows while preserving existing text.

- [ ] #15 Active/selected tab state composes with `Button` without `!important` — owner: Shared UI primitives — files: `frontend/src/shared/ui/Button/Button.module.css`, `frontend/src/features/admin/ui/AdminTabs.module.css`, `frontend/src/features/leaderboard/view.module.css` — risk: medium
  - Issue: `.active` / `.activeTab` override Button styles with `!important`, suppressing hover and focus transitions.
  - Change: Add a `selected` Button variant (or a lower-specificity state class) so active tabs compose cleanly with focus/hover rings.

- [ ] #16 Align reimplemented `Card` surfaces to the shared `Card` component — owner: Shared UI primitives — files: `frontend/src/shared/ui/Card/Card.tsx`, `frontend/src/features/leaderboard/view.module.css`, `frontend/src/features/history/view.module.css` — risk: medium
  - Issue: Leaderboard results panel and history panel redeclare gradient backgrounds, borders, radius, and shadow that already exist in `Card`.
  - Change: Use the shared `<Card>` component with a custom body class where internal padding needs removal; remove duplicated surface CSS.

- [ ] #17 Provide shared link-as-button styling for `Submissions` and `Session` — owner: Shared UI primitives — files: `frontend/src/shared/ui/Button/Button.module.css`, `frontend/src/features/submissions/view.module.css`, `frontend/src/features/submissions/view.tsx`, `frontend/src/features/session/view.module.css`, `frontend/src/features/session/view.tsx` — risk: medium
  - Issue: Both features recreate Button styling on anchors (`linkButton`, `submitLink`) and drift from the shared Button contract.
  - Change: Add a reusable `.buttonLink` / link-render mode to `Button` so anchors inherit hover, focus, active, and disabled states without duplication.

- [ ] #18 Card header titles should sit below page titles via shared size treatment — owner: Shared UI primitives — files: `frontend/src/shared/ui/Card/Card.module.css`, `frontend/src/features/submissions/view.tsx`, `frontend/src/features/session/view.tsx` — risk: low
  - Issue: Card headers render bare `<h2>` at browser default `1.5rem`, matching the explicitly styled page `<h1>` and flattening the heading hierarchy.
  - Change: Apply a default card-title style in `Card.module.css` (e.g., `1.125rem`, `font-weight: 700`) that still allows consumer overrides.

- [ ] #19 Button active and disabled visual states — owner: Shared UI primitives — files: `frontend/src/shared/ui/Button/Button.module.css` — risk: low
  - Issue: Buttons lack an `:active` pressed state and disabled buttons rely only on `opacity: 0.48`, which can be hard to read.
  - Change: Add `:active:not(:disabled)` feedback (subtle background shift or `translateY(1px)`) and pair disabled opacity with a muted surface/border colour or raise opacity to at least `0.6`.

- [ ] #20 DataTable selection a11y and hover affordance — owner: Shared UI primitives — files: `frontend/src/shared/ui/DataTable/DataTable.tsx`, `frontend/src/shared/ui/DataTable/DataTable.module.css` — risk: low
  - Issue: Selectable rows have a visual `.selectedRow` background but no `aria-selected`, and rows/sort headers have no hover state.
  - Change: Add `aria-selected={selected}` to selectable rows, subtle hover backgrounds to rows and sort buttons, and ensure focus rings are visible.

- [ ] #21 EmptyState and ErrorState heading-level prop — owner: Shared UI primitives — files: `frontend/src/shared/ui/EmptyState/EmptyState.tsx`, `frontend/src/shared/ui/ErrorState/ErrorState.tsx` — risk: low
  - Issue: Both components always render `<h3>`, which can skip heading levels depending on placement.
  - Change: Accept an optional `headingLevel` prop defaulting to `h3` so consumers can render `h1`/`h2`/`h4`.

- [ ] #22 Badge accessible name and status role — owner: Shared UI primitives — files: `frontend/src/shared/ui/Badge/Badge.tsx` — risk: medium
  - Issue: The badge uses `aria-label` on a generic `<span>`, which is unreliable and can override visible text.
  - Change: Remove the generic `aria-label`, optionally add `role="status"`, and render any prefix as visually hidden text inside the badge.

- [ ] #23 EmptyState status landmark — owner: Shared UI primitives — files: `frontend/src/shared/ui/EmptyState/EmptyState.tsx` — risk: low
  - Issue: `EmptyState` is a generic `<div>` with no role or live-region semantics.
  - Change: Add `role="status"` to the root so assistive technologies surface it when it appears dynamically.

- [ ] #24 SubmissionSourceDialog title association — owner: Shared UI primitives — files: `frontend/src/shared/ui/SubmissionSourceDialog/SubmissionSourceDialog.tsx` — risk: low
  - Issue: The dialog has both `aria-label={title}` and a visible `<h2>{title}</h2>`, causing duplicate announcements.
  - Change: Remove `aria-label`, add an `id` to the `<h2>`, and reference it with `aria-labelledby` on the dialog container.

- [ ] #25 PythonCodeBlock mono font token — owner: Shared UI primitives — files: `frontend/src/shared/ui/PythonCodeBlock/PythonCodeBlock.module.css` — risk: low
  - Issue: The code block hardcodes a mono stack instead of using the project's `--sf-font-mono` token.
  - Change: Replace the custom stack with `font-family: var(--sf-font-mono);`.

- [ ] #26 DataTable cell padding tokenization — owner: Shared UI primitives — files: `frontend/src/shared/ui/DataTable/DataTable.module.css` — risk: low
  - Issue: Cell padding mixes `10px` with `--sf-space-3`.
  - Change: Use `var(--sf-space-3)` on both axes or add a `--sf-space-2-5` token if `10px` is intentional.

- [ ] #27 ExecutionParametersTable empty state uses EmptyState — owner: Shared UI primitives — files: `frontend/src/shared/submissions/ExecutionParametersTable.tsx` — risk: low
  - Issue: When no execution parameters exist, the component renders a plain `<p>` instead of the shared `EmptyState`.
  - Change: Replace the paragraph with `<EmptyState>` using existing text strings (do not add new i18n keys).

- [ ] #28 Chart series colors map to theme tokens — owner: Shared charts — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx` — risk: medium
  - Issue: Strategy, benchmark, alpha, drawdown, profit, loss, and axis fallback colours are hardcoded hex literals.
  - Change: Map each series to semantic tokens (`--sf-cyan`, `--sf-amber`, `--sf-violet`, `--sf-emerald`, `--sf-profit`, `--sf-loss`).

- [ ] #29 Chart tooltip surfaces use theme tokens — owner: Shared charts — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`, `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.module.css` — risk: medium
  - Issue: Tooltip backgrounds, borders, and text are hardcoded for dark mode only.
  - Change: Replace hardcoded values with `--sf-overlay`, `--sf-border`, `--sf-text`, and `--sf-text-muted`.

- [ ] #30 Chart SVG grid/axis colors use theme tokens — owner: Shared charts — files: `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.module.css` — risk: medium
  - Issue: Grid lines, axis lines, and axis label fills use fixed slate RGBA values.
  - Change: Define chart tokens derived from `--sf-text-muted`/`--sf-border` (e.g., `color-mix(in srgb, var(--sf-text-muted) 16%, transparent)`) and apply them.

- [ ] #31 Chart profit/loss color convention — owner: Shared charts — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx` — risk: medium
  - Issue: `PROFIT_COLOR` is red and `LOSS_COLOR` is green, inverting finance conventions.
  - Change: Swap profit to emerald/green and loss to red, exposed as `--sf-profit` and `--sf-loss`.

- [ ] #32 Chart keyboard exploration and focus management — owner: Shared charts — files: `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.tsx` — risk: medium — deferred: requires new keyboard interaction behavior beyond pure visual polish; revisit in a dedicated a11y sprint.
  - Issue: The SVG is `aria-hidden` and tooltips only respond to pointer movement.
  - Change: Expose the SVG with `role="img"` and an `aria-label`, support Left/Right arrow navigation, and update the tooltip on focus.

- [ ] #33 Chart legend duplication and unavailable state — owner: Shared charts — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.module.css`, `frontend/src/shared/charts/LineChart/LineChart.module.css`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.module.css`, `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx` — risk: low
  - Issue: Legend styles are duplicated across three chart types, and unavailable items are only distinguished by opacity.
  - Change: Extract a shared legend stylesheet or component; add a non-colour unavailable indicator (strikethrough, parentheses, or icon) and visually hidden text.

- [ ] #34 Chart visible title and aria-labelledby — owner: Shared charts — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`, `frontend/src/shared/charts/LineChart/LineChart.tsx`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.tsx` — risk: low
  - Issue: The `title` prop is only exposed via `aria-label`; sighted users infer the chart subject from context.
  - Change: Render the title as visible text above each chart and associate it with the chart via `aria-labelledby`, keeping `aria-label` as fallback.

- [ ] #35 Chart reduced-motion for scroll-driven updates — owner: Shared charts — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx` — risk: low
  - Issue: Scroll-driven range updates rely on smooth-scroll behaviour with no reduced-motion guard.
  - Change: Honour `prefers-reduced-motion: reduce` by disabling smooth scroll and any scroll interpolation.

- [ ] #36 Chart tooltip aria-describedby and Escape dismissal — owner: Shared charts — files: `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.tsx` — risk: low
  - Issue: The tooltip `div` with `role="tooltip"` is not associated with the chart surface and cannot be dismissed with Escape.
  - Change: Add an `id` to the tooltip, reference it from the chart surface with `aria-describedby` when active, and support Escape dismissal.

- [ ] #37 Chart loading skeleton state — owner: Shared charts — files: `frontend/src/shared/charts/ComposedChart/ComposedChart.tsx`, `frontend/src/shared/charts/LineChart/LineChart.tsx`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.tsx` — risk: low
  - Issue: Charts handle only empty data and immediately render `EmptyState`, causing layout jumps while fetching.
  - Change: Add an optional `isLoading` prop that renders a chart-sized skeleton using `--sf-surface`/`--sf-surface-strong`.

- [ ] #38 Line/MultiLine chart overflow consistency — owner: Shared charts — files: `frontend/src/shared/charts/LineChart/LineChart.module.css`, `frontend/src/shared/charts/MultiLineChart/MultiLineChart.module.css` — risk: low
  - Issue: Chart frames use `overflow: auto`, which can show scrollbars from sub-pixel SVG sizing; `ComposedChart` uses `overflow: hidden`.
  - Change: Switch to `overflow: hidden` unless intentional scrolling is required.

- [ ] #39 Chart X-axis label overlap strategy — owner: Shared charts — files: `frontend/src/shared/charts/LightweightSvgChart/LightweightSvgChart.tsx` — risk: low — deferred: collision detection/rotation is a non-trivial layout change; defer until chart responsive strategy is defined.
  - Issue: X-axis labels render at a fixed size and always centered, so they can collide on narrow viewports.
  - Change: Implement label skipping/rotation or reduce font size based on available width and label count.

## Feature views

### Dashboard

- [ ] #40 KPI values use the model's semantic tone — owner: Dashboard — files: `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/dashboard/view.module.css` — risk: low
  - Issue: Every KPI value is rendered with the same cyan class even though the model provides `neutral`/`positive`/`warning`/`danger` tones.
  - Change: Add tone modifier classes and drive value colour from the model's `tone` prop.

- [ ] #41 Align latest submissions and live status surfaces — owner: Dashboard — files: `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/dashboard/view.module.css` — risk: low
  - Issue: Latest submissions uses `DataTable`'s flat bordered wrapper while live status sits inside a `<Card>` with gradient and shadow, giving the panels mismatched visual weight.
  - Change: Wrap both sections in the same surface treatment (either both in `<Card>` or both in a bordered wrapper).

- [ ] #42 `panelIntro` empty second row — owner: Dashboard — files: `frontend/src/features/dashboard/view.module.css`, `frontend/src/features/dashboard/view.tsx` — risk: low
  - Issue: `.panelIntro` reserves a `minmax(1.25rem, auto)` row that is empty for the live-status panel, creating uneven whitespace.
  - Change: Switch to a flex column with `gap` and remove the fixed row.

- [ ] #43 Course name truncation and styling — owner: Dashboard — files: `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/dashboard/view.module.css` — risk: low
  - Issue: The course name is a plain `<p>` with no class and can wrap indefinitely, unbalancing the header.
  - Change: Add a `.subtitle` class with muted colour, single-line truncation, and a sensible `max-width`.

- [ ] #44 Unknown status badges use a neutral tone — owner: Dashboard — files: `frontend/src/features/dashboard/view.tsx` — risk: medium
  - Issue: Unrecognized statuses fall back to the danger `"offline"` tone, visually implying failure.
  - Change: Map unknown statuses to a neutral/muted tone and reserve red for genuinely failed/offline states.

- [ ] #45 Dashboard mobile padding — owner: Dashboard — files: `frontend/src/features/dashboard/view.module.css` — risk: low
  - Issue: `.view` uses a fixed `padding: var(--sf-space-5)` that becomes excessive on small screens combined with shell padding.
  - Change: Add a mobile breakpoint (e.g., `max-width: 560px`) that reduces inner padding.

- [ ] #46 DataTable caption duplicates section heading — owner: Dashboard — files: `frontend/src/features/dashboard/view.tsx`, `frontend/src/shared/ui/DataTable/DataTable.tsx` — risk: low
  - Issue: The latest submissions section and the inner table caption use the same text, causing duplicate screen-reader announcements.
  - Change: Make the caption visually hidden but distinct (e.g., "Latest submissions table") or remove `aria-labelledby` from the section.

- [ ] #47 KPI values use tabular numerals — owner: Dashboard — files: `frontend/src/features/dashboard/view.module.css` — risk: low
  - Issue: Large numeric counts use proportional figures, so digits can shift as values update.
  - Change: Add `font-variant-numeric: tabular-nums;` to `.kpiValue`.

- [ ] #48 Live status icon colour — owner: Dashboard — files: `frontend/src/features/dashboard/view.tsx`, `frontend/src/features/dashboard/view.module.css` — risk: low
  - Issue: The decorative `Activity` icon inherits heading colour and misses a chance to reinforce liveness.
  - Change: Give the icon an explicit live colour (e.g., `var(--sf-emerald)`) or a small pulse indicator.

### Submissions

- [ ] #49 Environment download menu shadow token — owner: Submissions — files: `frontend/src/features/submissions/view.module.css` — risk: low
  - Issue: `.menu` declares a custom `box-shadow` instead of using `--sf-shadow` or a menu shadow token.
  - Change: Replace the raw shadow with `var(--sf-shadow)` (or a new `--sf-shadow-menu` token).

- [ ] #50 Data-track selection non-colour cue — owner: Submissions — files: `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submissions/view.module.css` — risk: medium
  - Issue: The selected track option only changes background colour, which is not sufficient for colour-vision deficiencies.
  - Change: Add a `Check` icon or a left border accent to the selected option.

- [ ] #51 Running-state icon animation — owner: Submissions — files: `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submissions/view.module.css` — risk: low
  - Issue: The running state shows a static `LoaderCircle` icon with no motion cue.
  - Change: Add a slow spin keyframe gated by `prefers-reduced-motion: no-preference`.

- [ ] #52 Environment download menu overflow — owner: Submissions — files: `frontend/src/features/submissions/view.module.css` — risk: low
  - Issue: The absolutely positioned menu can extend beyond the viewport on narrow screens when the trigger is not at the left edge.
  - Change: Anchor the menu to the right on narrow viewports or make it full-width below the trigger.

- [ ] #53 Track option hover feedback — owner: Submissions — files: `frontend/src/features/submissions/view.module.css` — risk: low
  - Issue: `.trackOption` has a selected state but no hover state.
  - Change: Add hover backgrounds for unselected and selected options using existing soft tokens.

- [ ] #54 Environment menu hints with icons — owner: Submissions — files: `frontend/src/features/submissions/view.tsx`, `frontend/src/features/submissions/view.module.css` — risk: low
  - Issue: Loading, error, and empty hints inside the dropdown are plain text with no icon.
  - Change: Pair each hint with a small icon (`LoaderCircle`, `AlertTriangle`, `PackageOpen`) and keep text compact.

- [ ] #55 Selected filename announced to assistive tech — owner: Submissions — files: `frontend/src/features/submissions/view.tsx` — risk: low
  - Issue: The selected filename appears visually but is not announced.
  - Change: Wrap the filename in `<span aria-live="polite">`.

### Session / login

- [ ] #56 Inline error compact sizing — owner: Session / login — files: `frontend/src/features/session/view.module.css`, `frontend/src/features/session/view.tsx` — risk: medium
  - Issue: The inline error renders the full-page `ErrorState`, which has a `min-height: 190px` and dominates the login card.
  - Change: Override the inline error container to `min-height: auto` and reduce vertical padding, or add a compact `ErrorState` size variant.

- [ ] #57 Required/autocomplete attributes on login inputs — owner: Session / login — files: `frontend/src/features/session/view.tsx` — risk: low
  - Issue: Team name and password inputs lack `required`/`aria-required` and `autoComplete` hints.
  - Change: Add `required autoComplete="username"` and `required autoComplete="current-password"`.

- [ ] #58 Login button loading spinner — owner: Session / login — files: `frontend/src/features/session/view.tsx`, `frontend/src/features/session/view.module.css` — risk: low
  - Issue: The button label changes to "Logging in..." but shows no spinner or motion cue.
  - Change: Render a spinning `LoaderCircle` beside the label during pending state, respecting `prefers-reduced-motion`.

- [ ] #59 Input hover and transitions — owner: Session / login — files: `frontend/src/features/session/view.module.css` — risk: low
  - Issue: `.input` has focus styles but no hover state or transition.
  - Change: Add `:hover { border-color: var(--sf-border-strong); }` and transition border/box-shadow.

- [ ] #60 Responsive view padding — owner: Session / login — files: `frontend/src/features/session/view.module.css` — risk: low
  - Issue: `.view` uses a flat `padding: var(--sf-space-4)` that feels cramped on desktop.
  - Change: Add a breakpoint (e.g., `min-width: 768px`) that increases padding.

- [ ] #61 Input elevated background token — owner: Session / login — files: `frontend/src/features/session/view.module.css` — risk: low
  - Issue: `.input` uses `--sf-bg`, which can blend into the card surface in light mode.
  - Change: Use `--sf-bg-elevated` for the input background in both themes.

### Submission detail

- [ ] #62 KPI neutral tone colour — owner: Submission detail — files: `frontend/src/features/submission-detail/ui/KpiCard.module.css` — risk: low
  - Issue: `.neutral` maps KPI value colour to `--sf-cyan`, making non-semantic KPIs compete with actions.
  - Change: Use `--sf-text-muted` or `--sf-text-secondary` for neutral values.

- [ ] #63 Stale/missing notices semantic warning style — owner: Submission detail — files: `frontend/src/features/submission-detail/view.module.css` — risk: medium
  - Issue: Warnings are rendered in muted text at `12px` and do not read as alerts.
  - Change: Introduce a warning notice variant using `--sf-amber` text on `--sf-amber-soft` with a matching border.

- [ ] #64 Panel header responsive stacking — owner: Submission detail — files: `frontend/src/features/submission-detail/view.module.css` — risk: medium
  - Issue: The panel header crams title, range controls, and toggles into one flex row that wraps awkwardly on narrow screens.
  - Change: Stack the header vertically below `640px` with controls left-aligned in a sub-row.

- [ ] #65 Toggle touch target size — owner: Submission detail — files: `frontend/src/features/submission-detail/view.module.css` — risk: medium
  - Issue: `.toggle` is `34px` tall with a `16px` checkbox, below the recommended `44px` touch target.
  - Change: Increase `.toggle` to at least `44px` and enlarge the clickable label area without reducing visible compactness.

- [ ] #66 Hardcoded group menu shadow — owner: Submission detail — files: `frontend/src/features/submission-detail/view.module.css` — risk: low
  - Issue: `.groupMenu` hardcodes a raw shadow value.
  - Change: Replace it with `var(--sf-shadow)`; remove related dead CSS if the group selector is unused.

- [ ] #67 Header badge mobile stacking — owner: Submission detail — files: `frontend/src/features/submission-detail/view.module.css` — risk: low
  - Issue: On small screens the badge can wrap to its own line and feel disconnected from the title block.
  - Change: Stack the header vertically on narrow viewports and place the badge below the metadata.

- [ ] #68 KPI card accessible name — owner: Submission detail — files: `frontend/src/features/submission-detail/ui/KpiCard.tsx` — risk: low
  - Issue: The value/label relationship is conveyed only by proximity.
  - Change: Add `aria-label={`${label}: ${value}`}` or visually hidden text so screen readers announce the KPI as one statement.

### History

- [ ] #69 Raw error modal a11y affordances — owner: History — files: `frontend/src/features/history/view.tsx` — risk: medium
  - Issue: The dialog lacks `aria-describedby`, initial focus on the close button, Escape dismissal, and backdrop-click dismissal.
  - Change: Add `aria-describedby` pointing to the `<pre>`, focus the close button on open, and handle Escape/backdrop click.

- [ ] #70 Raw error modal styling consistent with source-code dialog — owner: History — files: `frontend/src/features/history/view.tsx`, `frontend/src/features/history/view.module.css` — risk: medium
  - Issue: The raw error modal repeats dialog styling and a plain `<pre>` that differs from the source-code dialog experience.
  - Change: Mirror `SubmissionSourceDialog` styling (backdrop, header, body spacing) and render the error in the shared code-block surface.

- [ ] #71 Page/modal heading hierarchy — owner: History — files: `frontend/src/features/history/view.tsx` — risk: low
  - Issue: The page title and raw-error modal title are both `<h2>`, flattening the outline when the modal is open.
  - Change: Promote the page title to `<h1>` and keep the modal title as `<h2>`.

- [ ] #72 Toolbar responsive layout — owner: History — files: `frontend/src/features/history/view.module.css` — risk: low
  - Issue: Toolbar controls have a fixed `220px` min-width and `space-between` causes ragged wrapping on narrow viewports.
  - Change: Use a responsive flex/grid layout, reduce `min-width` on small screens, and align wrapped rows to `flex-start`.

- [ ] #73 Error message semantic colour — owner: History — files: `frontend/src/features/history/view.module.css` — risk: low
  - Issue: `.errorText` uses `--sf-text-muted`, causing error descriptions to recede visually.
  - Change: Use `--sf-red` (or a future `--sf-text-danger` token) for error text, or lead with a warning-coloured icon.

- [ ] #74 Disabled account toggle helper — owner: History — files: `frontend/src/features/history/view.tsx`, `frontend/src/features/history/view.module.css` — risk: low
  - Issue: The disabled "My submissions only" toggle only communicates its reason through a `title` tooltip, which is inaccessible to keyboard/touch users.
  - Change: Render persistent visible helper text using existing copy and associate it with the checkbox via `aria-describedby`.

- [ ] #75 Panel gradient to token — owner: History — files: `frontend/src/theme/tokens.css`, `frontend/src/features/history/view.module.css` — risk: low
  - Issue: `.panel` uses a hardcoded gradient not represented in tokens.
  - Change: Replace the gradient with a solid token or introduce `--sf-panel-surface` and apply it.

- [ ] #76 Search placeholder colour — owner: History — files: `frontend/src/features/history/view.module.css` — risk: low
  - Issue: The search input relies on the browser-default placeholder colour, which may fail contrast on the dark surface.
  - Change: Add `::placeholder { color: var(--sf-text-muted); opacity: 1; }`.

- [ ] #77 Panel header mobile stacking — owner: History — files: `frontend/src/features/history/view.tsx`, `frontend/src/features/history/view.module.css` — risk: low
  - Issue: `.panelHeader` can leave the compare button dangling at the far edge on narrow screens.
  - Change: Add a mobile breakpoint that switches to a column layout with a full-width button.

- [ ] #78 Raw error modal transitions — owner: History — files: `frontend/src/features/history/view.module.css` — risk: low
  - Issue: The modal appears instantly with no opacity or transform transition.
  - Change: Add opacity/translate transitions gated by `prefers-reduced-motion`.

- [ ] #79 Header `justify-content` cleanup — owner: History — files: `frontend/src/features/history/view.module.css` — risk: low
  - Issue: `.header` uses `space-between` but contains only one flex child.
  - Change: Remove the redundant declaration or add a second header action.

### Leaderboard

- [ ] #80 Metric tabs ARIA — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.tsx` — risk: low
  - Issue: Tabs have `role="tablist"`/`role="tab"`/`aria-selected` but lack `aria-controls` and the panel is not a `role="tabpanel"`.
  - Change: Add `aria-controls` to each tab and convert the results section to `role="tabpanel"` with `aria-labelledby`.

- [ ] #81 Toolbar wrapping/orphan button — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.module.css` — risk: low
  - Issue: `.toolbar` uses `space-between` so the compare button can wrap to the far right and look detached.
  - Change: Group controls and use `margin-left: auto` for the compare group, or stack at an intermediate breakpoint.

- [ ] #82 Dynamic search/sort announcements — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.tsx` — risk: medium
  - Issue: Search and sort updates modify the table without announcing result count or sort direction.
  - Change: Add a polite `aria-live` region near the table header that announces filtered/sorted state.

- [ ] #83 Empty state distinction — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.tsx` — risk: low
  - Issue: "No submissions" and "no search matches" render the same empty-state copy.
  - Change: Provide two `EmptyState` variants using existing strings and a visible clear-search affordance when the search input is non-empty.

- [ ] #84 Healthy standby neutral badge tone — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.tsx` — risk: medium
  - Issue: A healthy, fully-scored leaderboard renders an amber "degraded" badge.
  - Change: Use a neutral/positive tone for healthy standby and reserve amber for genuinely degraded/stale states.

- [ ] #85 Rank medal tier differentiation — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.tsx`, `frontend/src/features/leaderboard/view.module.css` — risk: low
  - Issue: Gold, silver, and bronze medals use the same icon and styling.
  - Change: Assign distinct icon colours or small tier labels while keeping the rank number clear.

- [ ] #86 Responsive breakpoints — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.module.css` — risk: low
  - Issue: Only one narrow breakpoint exists, leaving intermediate widths cramped.
  - Change: Add an intermediate breakpoint (e.g., `768px`) that stacks the toolbar earlier.

- [ ] #87 Pagination footer separation — owner: Leaderboard — files: `frontend/src/features/leaderboard/view.module.css` — risk: low
  - Issue: The pagination footer sits directly below the panel with no visual boundary.
  - Change: Add a subtle top border or background surface to the pagination bar.

### Compare

- [ ] #88 Detail toolbar alignment — owner: Compare — files: `frontend/src/features/compare/view.module.css` — risk: low
  - Issue: `.detailToolbar` uses `align-items: flex-end`, forcing the small selector label and taller controls onto their bottom edges.
  - Change: Switch to `align-items: center` (or `baseline`) and let control padding establish rhythm.

- [ ] #89 Panel header colour cleanup — owner: Compare — files: `frontend/src/features/compare/view.module.css` — risk: low
  - Issue: `.panelHeader` sets `color: var(--sf-cyan)` but `.panelTitle` overrides it, so only the icon inherits cyan.
  - Change: Remove the container colour and apply cyan explicitly to the icon via a dedicated class.

- [ ] #90 Custom toggle hover/focus — owner: Compare — files: `frontend/src/features/compare/view.module.css` — risk: low
  - Issue: `.toggle` provides no hover, focus-within, or active states beyond the native checkbox.
  - Change: Add hover background, `:focus-within` ring wrapping the whole toggle, and a transition.

- [ ] #91 Card/KPI grid overflow — owner: Compare — files: `frontend/src/features/compare/view.module.css` — risk: medium
  - Issue: `.cardGrid` can force overflow below `280px` plus gaps; `.kpiGrid` squeezes cells on very narrow cards.
  - Change: Use `minmax(min(280px, 100%), 1fr)` for cards and stack KPIs below `360px`.

- [ ] #92 Segmented control touch targets — owner: Compare — files: `frontend/src/features/compare/view.module.css` — risk: low
  - Issue: `.segmented button` is `32px` tall, below the recommended touch target.
  - Change: Increase `min-height` to at least `40px` (ideally `44px`) and add a matching `min-width`.

- [ ] #93 Difference values semantic colour — owner: Compare — files: `frontend/src/features/compare/view.tsx`, `frontend/src/features/compare/view.module.css` — risk: low
  - Issue: The `diff` column shows signed numbers with no colour or icon treatment.
  - Change: Apply semantic colours to diff cells (positive emerald, negative red, zero muted) while keeping the explicit sign.

- [ ] #94 Transitions and reduced-motion — owner: Compare — files: `frontend/src/features/compare/view.module.css` — risk: low
  - Issue: Toggle, select, and segmented buttons have no transitions and no reduced-motion guard.
  - Change: Add `transition` for background/border/box-shadow and wrap them in a `prefers-reduced-motion: reduce` block.

- [ ] #95 Redundant toggle aria-label — owner: Compare — files: `frontend/src/features/compare/view.tsx` — risk: low
  - Issue: The checkbox inside a wrapping `<label>` also carries an identical `aria-label`.
  - Change: Remove the redundant `aria-label` and rely on the visible label.

- [ ] #96 Card accent fallback — owner: Compare — files: `frontend/src/features/compare/view.tsx`, `frontend/src/features/compare/view.module.css` — risk: low
  - Issue: `.cardAccent` receives an inline `backgroundColor` with no CSS fallback.
  - Change: Set a default `background-color: var(--sf-cyan)` in the module and let the inline style override it.

### Admin console

- [ ] #97 AdminTabs nav landmark — owner: Admin console — files: `frontend/src/features/admin/ui/AdminTabs.tsx` — risk: low
  - Issue: The tab strip is wrapped in `<nav>` but immediately given `role="tablist"`, overriding the navigation landmark.
  - Change: Keep `<nav aria-label="...">` and move `role="tablist"` to an inner `<div>`.

- [ ] #98 Status group role/logout placement — owner: Admin console — files: `frontend/src/features/admin/view.tsx`, `frontend/src/features/admin/cohortSubmissionsView.tsx` — risk: low
  - Issue: The `.status` `<div>` has `aria-label` but no `role` and mixes metadata with the interactive Logout button.
  - Change: Give the metadata wrapper `role="group"` and move the logout `Button` outside the group; apply the same fix for the cohort back link.

- [ ] #99 Raw-error dialog `aria-labelledby` — owner: Admin console — files: `frontend/src/features/admin/ui/SubmissionsPanel.tsx` — risk: low
  - Issue: The dialog uses `aria-label` while the visible `<h2>` has no `id`.
  - Change: Add an `id` to the dialog `<h2>` and reference it with `aria-labelledby`.

- [ ] #100 Plain anchor links styled as buttons — owner: Admin console — files: `frontend/src/features/admin/ui/TeamsPanel.tsx`, `frontend/src/features/admin/cohortSubmissionsView.tsx` — risk: low
  - Issue: "View submissions" and back links are unstyled anchors next to styled buttons.
  - Change: Render the links with a button-like class or use the shared `Button` link treatment.

- [ ] #101 Dataset toast semantic soft surfaces — owner: Admin console — files: `frontend/src/features/admin/view.module.css` — risk: low
  - Issue: Success/error toasts only change border/icon colour while the background stays `--sf-surface`.
  - Change: Use `--sf-emerald-soft` for success and `--sf-red-soft` for error backgrounds.

- [ ] #102 Dataset toast reduced-motion spinner — owner: Admin console — files: `frontend/src/features/admin/view.module.css` — risk: low
  - Issue: `.datasetToastSpinner` animates infinitely with no reduced-motion guard.
  - Change: Wrap the spin keyframes inside `prefers-reduced-motion: no-preference`; show a static processing icon otherwise.

- [ ] #103 Toast and loading entry/exit transitions — owner: Admin console — files: `frontend/src/features/admin/ui/Panels.module.css`, `frontend/src/features/admin/view.tsx` — risk: low
  - Issue: Toasts and loading containers mount/unmount instantly.
  - Change: Add opacity/transform transitions with reduced-motion fallback and a polite status region for the loading state.

- [ ] #104 Form field fixed min-height — owner: Admin console — files: `frontend/src/features/admin/ui/Panels.module.css` — risk: low
  - Issue: `.field` sets `min-height: 78px`, creating uneven rhythm when labels wrap.
  - Change: Remove the fixed min-height and rely on `gap`/margin for alignment.

- [ ] #105 Table min-width responsive — owner: Admin console — files: `frontend/src/features/admin/ui/Panels.module.css` — risk: low
  - Issue: `.table` has `min-width: 1120px`, causing horizontal overflow between `900px` and `1120px`.
  - Change: Make `min-width` responsive or allow columns to narrow at a larger breakpoint.

### App shell & routing

- [ ] #116 Styled route Suspense fallback — owner: App shell & routing — files: `frontend/src/routes.tsx` — risk: low
  - Issue: The lazy-route fallback is an unstyled bare `<div>` with translated text.
  - Change: Replace it with a centered loading placeholder using theme tokens, an animated spinner, `role="status"`, `aria-live="polite"`, and reduced-motion fallback.

- [ ] #117 Styled route error boundary — owner: App shell & routing — files: `frontend/src/routes.tsx`, `frontend/src/shared/ui/ErrorState/ErrorState.module.css` — risk: medium
  - Issue: Failed lazy routes fall back to React Router's default unstyled error UI.
  - Change: Add a design-token-styled `errorElement` using the shared `ErrorState` surface and a "Retry" button.

- [ ] #118 Programmatic route focus target — owner: App shell & routing — files: `frontend/src/app/App.tsx`, `frontend/src/shared/layout/Shell.tsx` — risk: medium — deferred: requires new routing focus-management behavior beyond visual polish; revisit in a11y sprint.
  - Issue: There is no focusable content landmark to receive focus on route changes.
  - Change: Wrap `<Outlet />` in a `<main>`/`<div role="main">` with `tabIndex={-1}` and move focus there on location change.

- [ ] #119 Route transition animation — owner: App shell & routing — files: `frontend/src/routes.tsx`, `frontend/src/app/App.tsx` — risk: low — deferred: risk of jank with data-heavy views; evaluate after performance baseline.
  - Issue: Route content swaps instantly with no transition.
  - Change: Add a short cross-fade/slide-in transition around `<Outlet />`, gated by `prefers-reduced-motion`.

---

## Summary

- **Total backlog items:** 119
- **Deferred items:** 6
- **Risk distribution:**
  - High: 0
  - Medium: 30
  - Low: 89

- **Items per owner scope:**
  - Theme & global tokens: 8
  - Layout shell: 5
  - Shared UI primitives: 14
  - Shared charts: 12
  - Dashboard: 9
  - Submissions: 7
  - Session / login: 6
  - Submission detail: 7
  - History: 11
  - Leaderboard: 8
  - Compare: 9
  - Admin console: 10
  - Mini-games: 9
  - App shell & routing: 4
