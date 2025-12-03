export function randomHexColor() {
  return `#${Math.floor(Math.random() * 0xffffff)
    .toString(16)
    .padStart(6, "0")}`;
}

// Helper function to get marker color based on confidence score
export function getMarkerColorByConfidence(score: number | undefined): string {
  // Default to low confidence if score is undefined
  const confidence = score ?? 0;

  if (confidence > 0.6) {
    return "#17C964"; // High confidence (above 0.55)
  } else if (confidence >= 0.5 && confidence <= 0.6) {
    return "#F5A524"; // Medium confidence (between 0.5 and 0.55)
  } else {
    return "#C20E4D"; // Low confidence (below 0.5)
  }
}
