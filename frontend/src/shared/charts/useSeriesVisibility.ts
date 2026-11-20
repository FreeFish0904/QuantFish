import { useState } from "react";

export type SeriesVisibility = {
  alpha: boolean;
  benchmark: boolean;
};

const HIDDEN: SeriesVisibility = { alpha: false, benchmark: false };

/**
 * Toggle state for the benchmark/alpha overlays on a chart.
 *
 * The choice belongs to one submission, so it is stored together with the `key`
 * it was made for (submission id plus the series that submission can offer).
 * When the key changes the stored choice no longer applies and both overlays
 * start hidden again -- derived during render, so the toolbar never paints a
 * frame with a stale checkbox and no effect has to reset the state.
 */
export function useSeriesVisibility(key: string): {
  setAlpha: (alpha: boolean) => void;
  setBenchmark: (benchmark: boolean) => void;
  visibility: SeriesVisibility;
} {
  const [stored, setStored] = useState<{ key: string; visibility: SeriesVisibility } | null>(null);
  const visibility = stored?.key === key ? stored.visibility : HIDDEN;
  return {
    setAlpha: (alpha) => setStored({ key, visibility: { ...visibility, alpha } }),
    setBenchmark: (benchmark) => setStored({ key, visibility: { ...visibility, benchmark } }),
    visibility
  };
}
