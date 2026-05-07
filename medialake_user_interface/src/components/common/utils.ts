export function randomHexColor() {
  return `#${Math.floor(Math.random() * 0xffffff)
    .toString(16)
    .padStart(6, "0")}`;
}

// Centralized confidence score colors
// Used by both the confidence slider legend and clip markers
export const CONFIDENCE_COLORS = {
  HIGH: "#17C964", // Green - High confidence
  MEDIUM: "#F5A524", // Orange - Medium confidence
  LOW: "#C20E4D", // Red - Low confidence
} as const;

// Model-specific confidence thresholds
// Different embedding models produce different score distributions
// MIN/MAX define the slider range per model
export const MODEL_THRESHOLDS = {
  // Marengo 3.0 produces scores in a narrower range (0.45-0.60)
  "3.0": {
    MIN: 0.4, // Slider minimum
    MAX: 0.6, // Slider maximum
    HIGH: 0.55, // Best matches are typically 0.55+
    MEDIUM: 0.48, // Medium matches are 0.48-0.55
    DEFAULT_CONFIDENCE: 0.5, // Default slider starting position
  },
  // Marengo 2.7 and other models produce scores in a wider range (0.45-0.70)
  // This is also the default for clips without model_version (legacy data)
  "2.7": {
    MIN: 0.4, // Slider minimum
    MAX: 0.75, // Slider maximum
    HIGH: 0.6, // Best matches are typically 0.60+
    MEDIUM: 0.5, // Medium matches are 0.50-0.60
    DEFAULT_CONFIDENCE: 0.57, // Default slider starting position
  },
} as const;

// Type for model version
export type ModelVersion = "3.0" | "2.7";

// Get thresholds for a specific model version
// If modelVersion is undefined/missing, defaults to 2.7 thresholds (legacy behavior)
export function getThresholdsForModel(modelVersion?: string): {
  MIN: number;
  MAX: number;
  HIGH: number;
  MEDIUM: number;
  DEFAULT_CONFIDENCE: number;
} {
  if (modelVersion === "3.0") {
    return MODEL_THRESHOLDS["3.0"];
  }
  // Default to 2.7 thresholds for undefined, "2.7", or any other value
  // This maintains backward compatibility with legacy data that doesn't have model_version
  return MODEL_THRESHOLDS["2.7"];
}

// Legacy export for backward compatibility (uses 2.7/default thresholds)
export const CONFIDENCE_THRESHOLDS = MODEL_THRESHOLDS["2.7"];

// Helper function to get marker color based on confidence score
// Supports model-aware thresholds when modelVersion is provided
// If modelVersion is undefined, uses 2.7 thresholds (legacy behavior)
export function getMarkerColorByConfidence(
  score: number | undefined,
  modelVersion?: string
): string {
  const confidence = score ?? 0;
  const thresholds = getThresholdsForModel(modelVersion);

  if (confidence >= thresholds.HIGH) {
    return CONFIDENCE_COLORS.HIGH;
  } else if (confidence >= thresholds.MEDIUM) {
    return CONFIDENCE_COLORS.MEDIUM;
  } else {
    return CONFIDENCE_COLORS.LOW;
  }
}

// Helper function to get confidence label based on score
// Supports model-aware thresholds when modelVersion is provided
// If modelVersion is undefined, uses 2.7 thresholds (legacy behavior)
export function getConfidenceLabel(score: number | undefined, modelVersion?: string): string {
  const confidence = score ?? 0;
  const thresholds = getThresholdsForModel(modelVersion);

  if (confidence >= thresholds.HIGH) {
    return "High";
  } else if (confidence >= thresholds.MEDIUM) {
    return "Medium";
  } else {
    return "Low";
  }
}
