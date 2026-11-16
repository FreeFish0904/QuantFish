import { describe, expect, it } from "vitest";

import {
  DATA_TRACKS,
  dataTrackLabelKey,
  dataTrackSearchText,
  isDataTrack,
  isLearningDataTrack,
  normalizeDataTrack
} from "./dataTrack";

describe("data tracks", () => {
  it("recognizes every server-supported track without collapsing learning windows", () => {
    expect(DATA_TRACKS).toEqual([
      "hidden_test",
      "learning",
      "learning_1",
      "learning_2",
      "learning_3"
    ]);

    for (const track of DATA_TRACKS) {
      expect(isDataTrack(track)).toBe(true);
      expect(normalizeDataTrack(track)).toBe(track);
    }
    expect(isDataTrack("learning_4")).toBe(false);
    expect(normalizeDataTrack("learning_4")).toBe("hidden_test");
  });

  it("keeps labels, search aliases, and learning-family behavior centralized", () => {
    expect(dataTrackLabelKey("learning_2")).toBe("common.learningWindow2Track");
    expect(dataTrackSearchText("learning_2")).toContain("2015 2020");
    expect(isLearningDataTrack("learning_2")).toBe(true);
    expect(isLearningDataTrack("hidden_test")).toBe(false);
  });
});
