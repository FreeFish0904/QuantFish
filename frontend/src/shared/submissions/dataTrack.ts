export const DATA_TRACKS = [
  "hidden_test",
  "learning",
  "learning_1",
  "learning_2",
  "learning_3"
] as const;

export type DataTrack = (typeof DATA_TRACKS)[number];
type DataTrackLabelKey =
  | "common.hiddenTestTrack"
  | "common.learningDataTrack"
  | "common.learningWindow1Track"
  | "common.learningWindow2Track"
  | "common.learningWindow3Track";

const DATA_TRACK_LABEL_KEYS: Record<DataTrack, DataTrackLabelKey> = {
  hidden_test: "common.hiddenTestTrack",
  learning: "common.learningDataTrack",
  learning_1: "common.learningWindow1Track",
  learning_2: "common.learningWindow2Track",
  learning_3: "common.learningWindow3Track"
};

export function isDataTrack(value: unknown): value is DataTrack {
  return typeof value === "string" && DATA_TRACKS.includes(value as DataTrack);
}

export function normalizeDataTrack(value: string | null | undefined): DataTrack {
  return isDataTrack(value) ? value : "hidden_test";
}

export function isLearningDataTrack(track: DataTrack): boolean {
  return track !== "hidden_test";
}

export function dataTrackLabelKey(track: DataTrack): DataTrackLabelKey {
  return DATA_TRACK_LABEL_KEYS[track];
}

export function dataTrackSearchText(track: DataTrack): string {
  return {
    hidden_test: "hidden test hidden_test",
    learning: "learning data learning",
    learning_1: "learning window 1 learning_1 2010 2015",
    learning_2: "learning window 2 learning_2 2015 2020",
    learning_3: "learning window 3 learning_3 2020 2022"
  }[track];
}
