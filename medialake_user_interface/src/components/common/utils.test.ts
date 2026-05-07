import { describe, it, expect } from "vitest";
import {
  getThresholdsForModel,
  getMarkerColorByConfidence,
  getConfidenceLabel,
  CONFIDENCE_COLORS,
  MODEL_THRESHOLDS,
} from "./utils";

describe("getThresholdsForModel", () => {
  it("returns 3.0 thresholds for model version 3.0", () => {
    const t = getThresholdsForModel("3.0");
    expect(t).toEqual(MODEL_THRESHOLDS["3.0"]);
  });

  it("returns 2.7 thresholds for model version 2.7", () => {
    const t = getThresholdsForModel("2.7");
    expect(t).toEqual(MODEL_THRESHOLDS["2.7"]);
  });

  it("defaults to 2.7 thresholds for undefined", () => {
    expect(getThresholdsForModel(undefined)).toEqual(MODEL_THRESHOLDS["2.7"]);
  });

  it("defaults to 2.7 thresholds for unknown version", () => {
    expect(getThresholdsForModel("1.0")).toEqual(MODEL_THRESHOLDS["2.7"]);
  });
});

describe("getMarkerColorByConfidence", () => {
  it("returns HIGH color for high scores (2.7 model)", () => {
    expect(getMarkerColorByConfidence(0.65, "2.7")).toBe(CONFIDENCE_COLORS.HIGH);
  });

  it("returns MEDIUM color for medium scores (2.7 model)", () => {
    expect(getMarkerColorByConfidence(0.55, "2.7")).toBe(CONFIDENCE_COLORS.MEDIUM);
  });

  it("returns LOW color for low scores (2.7 model)", () => {
    expect(getMarkerColorByConfidence(0.3, "2.7")).toBe(CONFIDENCE_COLORS.LOW);
  });

  it("returns HIGH color for high scores (3.0 model)", () => {
    expect(getMarkerColorByConfidence(0.56, "3.0")).toBe(CONFIDENCE_COLORS.HIGH);
  });

  it("returns MEDIUM color for medium scores (3.0 model)", () => {
    expect(getMarkerColorByConfidence(0.5, "3.0")).toBe(CONFIDENCE_COLORS.MEDIUM);
  });

  it("returns LOW color for low scores (3.0 model)", () => {
    expect(getMarkerColorByConfidence(0.4, "3.0")).toBe(CONFIDENCE_COLORS.LOW);
  });

  it("treats undefined score as 0 (LOW)", () => {
    expect(getMarkerColorByConfidence(undefined)).toBe(CONFIDENCE_COLORS.LOW);
  });

  it("defaults to 2.7 thresholds when no model specified", () => {
    // 0.55 is MEDIUM for 2.7 (threshold is 0.5) but HIGH for 3.0 (threshold is 0.55)
    expect(getMarkerColorByConfidence(0.55)).toBe(CONFIDENCE_COLORS.MEDIUM);
  });
});

describe("getConfidenceLabel", () => {
  it("returns 'High' for high scores", () => {
    expect(getConfidenceLabel(0.65, "2.7")).toBe("High");
  });

  it("returns 'Medium' for medium scores", () => {
    expect(getConfidenceLabel(0.55, "2.7")).toBe("Medium");
  });

  it("returns 'Low' for low scores", () => {
    expect(getConfidenceLabel(0.3, "2.7")).toBe("Low");
  });

  it("treats undefined score as 0 (Low)", () => {
    expect(getConfidenceLabel(undefined)).toBe("Low");
  });

  it("uses 3.0 thresholds when specified", () => {
    // 0.56 is HIGH for 3.0 (threshold 0.55) but MEDIUM for 2.7 (threshold 0.6)
    expect(getConfidenceLabel(0.56, "3.0")).toBe("High");
    expect(getConfidenceLabel(0.56, "2.7")).toBe("Medium");
  });
});
