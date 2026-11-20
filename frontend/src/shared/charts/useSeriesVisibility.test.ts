import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSeriesVisibility } from "./useSeriesVisibility";

describe("useSeriesVisibility", () => {
  it("starts hidden and remembers the choice for the key it was made for", () => {
    const { result, rerender } = renderHook(
      ({ seriesKey }: { seriesKey: string }) => useSeriesVisibility(seriesKey),
      { initialProps: { seriesKey: "submission-a:true:true:false" } }
    );

    expect(result.current.visibility).toEqual({ alpha: false, benchmark: false });

    act(() => result.current.setBenchmark(true));
    expect(result.current.visibility).toEqual({ alpha: false, benchmark: true });

    rerender({ seriesKey: "submission-a:true:true:false" });
    expect(result.current.visibility.benchmark).toBe(true);
  });

  it("starts hidden again when the key refers to another submission", () => {
    const { result, rerender } = renderHook(
      ({ seriesKey }: { seriesKey: string }) => useSeriesVisibility(seriesKey),
      { initialProps: { seriesKey: "submission-a" } }
    );

    act(() => result.current.setBenchmark(true));
    act(() => result.current.setAlpha(true));
    expect(result.current.visibility).toEqual({ alpha: true, benchmark: true });

    rerender({ seriesKey: "submission-b" });
    expect(result.current.visibility).toEqual({ alpha: false, benchmark: false });

    rerender({ seriesKey: "submission-a" });
    expect(result.current.visibility).toEqual({ alpha: true, benchmark: true });
  });

  it("toggles one series without disturbing the other", () => {
    const { result } = renderHook(() => useSeriesVisibility("submission-a"));

    act(() => result.current.setAlpha(true));
    act(() => result.current.setBenchmark(true));
    act(() => result.current.setAlpha(false));

    expect(result.current.visibility).toEqual({ alpha: false, benchmark: true });
  });
});
