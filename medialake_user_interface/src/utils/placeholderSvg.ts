/**
 * Utility functions for generating SVG placeholder images
 */

/**
 * Creates a data URL for an SVG placeholder image
 * @param width - Width of the placeholder
 * @param height - Height of the placeholder
 * @param text - Text to display in the placeholder
 * @param backgroundColor - Background color (default: #DDDDDD)
 * @param textColor - Text color (default: #999999)
 * @returns Data URL string for the SVG
 */
export function createPlaceholderSvg(
  width: number = 300,
  height: number = 200,
  text: string = "Placeholder",
  backgroundColor: string = "#DDDDDD",
  textColor: string = "#999999",
): string {
  const fontSize = Math.min(width, height) * 0.12; // Responsive font size

  const svg = `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="${backgroundColor}"/>
  <text x="50%" y="50%" font-family="Arial, sans-serif" font-size="${fontSize}" font-weight="bold" fill="${textColor}" text-anchor="middle" dominant-baseline="middle">${text}</text>
</svg>`;

  return `data:image/svg+xml;base64,${btoa(svg)}`;
}

/**
 * Creates a standard placeholder image (300x200)
 */
export const PLACEHOLDER_IMAGE = createPlaceholderSvg(300, 200, "Placeholder");

/**
 * Creates a video placeholder image (300x200)
 */
export const VIDEO_PLACEHOLDER_IMAGE = createPlaceholderSvg(
  300,
  200,
  "Placeholder",
);

/**
 * Creates a small timecode placeholder for video scrubbing (100x56)
 * @param timeString - The timecode string to display
 */
export function createTimecodePlaceholder(timeString: string): string {
  return createPlaceholderSvg(100, 56, timeString, "#000000", "#FFFFFF");
}
