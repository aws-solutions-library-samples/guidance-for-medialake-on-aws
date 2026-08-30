/**
 * Timecode formatting and parsing — the single source of truth for how a point
 * in time or a clip range is rendered anywhere in the UI.
 *
 * This module exists because the same job was previously done by five separate
 * local implementations that disagreed with each other:
 *
 *   - `AssetSidebar.formatSecondsToTimecode` — HH:MM:SS:FF, frames at a
 *     hardcoded 30fps, while every other part of the app assumed 25.
 *   - `AssetSidebar.formatSegmentInfo` — M:SS with frames discarded.
 *   - `BatchOperations.formatClock` — M:SS with no hours carry, so a clip an
 *     hour into an asset rendered as "65:00".
 *   - `AssetAudio.formatTime` — M:SS, minutes not zero padded.
 *   - `clipTransformation.getClipDisplayName` — a fourth M:SS copy.
 *
 * Conventions settled on here, so the same clip reads the same way in the
 * selection bin, the add-to-collection modal, a collection listing and the
 * asset detail sidebar:
 *
 *   - Clock displays always carry hours once the time reaches an hour, and
 *     never silently overflow the minutes field.
 *   - Ranges use an en dash flanked by narrow no-break spaces
 *     (`00:01:05 – 00:02:10`), not an ASCII hyphen, so a range is not mistaken
 *     for a negative number or a hyphenated filename, and never wraps mid-value.
 *   - Frames are shown only where frame accuracy is actionable (editing a
 *     marker, or a tooltip on a source timecode). At list density they are
 *     noise, and for segments derived from seconds they are fabricated `:00`.
 *   - Frame counts are derived from the asset's real frame rate when it is
 *     known, falling back to `DEFAULT_FPS`.
 */

/**
 * Frame rate assumed when an asset does not report one.
 *
 * 25 matches the rest of the codebase (`markerHelpers`, the Omakase player
 * load options, the player keyboard-shortcut shuttle) rather than the 30 the
 * old sidebar formatter used.
 */
export const DEFAULT_FPS = 25;

/**
 * A full SMPTE timecode: `HH:MM:SS:FF`, or `HH:MM:SS;FF` for drop-frame.
 *
 * Kept permissive on the hours field (1 or 2 digits) because timecodes reach
 * the UI from several producers.
 */
export const SMPTE_TIMECODE_RE = /^\d{1,2}:\d{2}:\d{2}[:;]\d{2}$/;

/**
 * The canonical range separator: an en dash flanked by narrow no-break spaces
 * (U+202F).
 *
 * The narrow spaces are deliberate -- they read tighter than a normal space and
 * suppress a break *before* the dash. They are not sufficient on their own,
 * though: Chromium still takes the line-break opportunity UAX #14 allows
 * immediately *after* an en dash, so any surface rendering a range in a
 * constrained box also needs `white-space: nowrap`. See the collection table's
 * Timecode column for the pattern.
 */
export const RANGE_SEPARATOR = "\u202f\u2013\u202f";

export interface FormatTimecodeOptions {
  /** Append `:FF`. Requires a frame rate to be meaningful. */
  showFrames?: boolean;
  /** Frame rate used for the frames field. Defaults to `DEFAULT_FPS`. */
  fps?: number;
  /**
   * Always emit the hours group, even below an hour. Off by default so short
   * clips read as `01:05` rather than `00:01:05`; forced on whenever frames are
   * shown, since a partial SMPTE timecode is worse than a verbose one.
   */
  alwaysShowHours?: boolean;
}

const pad = (value: number, width = 2): string => String(value).padStart(width, "0");

/**
 * True when `value` is a usable, finite, non-negative number of seconds.
 *
 * Guards every entry point: seconds arrive from search payloads, player state
 * and hand-edited fields, so `NaN`, `Infinity` and negatives all show up.
 */
export const isValidTime = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;

/**
 * Resolve a usable frame rate, rejecting values that would produce nonsense
 * frame numbers.
 */
const resolveFps = (fps?: number): number =>
  typeof fps === "number" && Number.isFinite(fps) && fps > 0 ? fps : DEFAULT_FPS;

/**
 * Format seconds as a clock.
 *
 * Below an hour: `MM:SS`. At or above an hour: `H:MM:SS`. Minutes never exceed
 * 59 — the bug this replaces rendered a 65-minute offset as `65:00`.
 *
 * Returns `null` for unusable input so callers can decide whether to omit the
 * element entirely rather than render a misleading `0:00`.
 */
export function formatTimecode(
  seconds: number | null | undefined,
  options: FormatTimecodeOptions = {}
): string | null {
  if (!isValidTime(seconds)) return null;

  const { showFrames = false, fps, alwaysShowHours = false } = options;

  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  // A timecode carrying frames is a SMPTE timecode, and SMPTE is always
  // fully qualified — emitting `01:05:12` for MM:SS:FF would be ambiguous.
  const withHours = showFrames || alwaysShowHours || hours > 0;

  const clock = withHours
    ? `${pad(hours)}:${pad(minutes)}:${pad(secs)}`
    : `${pad(minutes)}:${pad(secs)}`;

  if (!showFrames) return clock;

  const effectiveFps = resolveFps(fps);
  // Clamp: floating point drift on a value like 9.9999 would otherwise yield a
  // frame number equal to the frame rate, which is not a valid frame index.
  const frames = Math.min(Math.floor((seconds % 1) * effectiveFps), Math.ceil(effectiveFps) - 1);

  return `${clock}:${pad(Math.max(0, frames))}`;
}

/**
 * Format seconds as a full SMPTE timecode (`HH:MM:SS:FF`).
 *
 * Convenience wrapper for the frame-accurate case; returns `null` on unusable
 * input like `formatTimecode`.
 */
export function formatSmpte(seconds: number | null | undefined, fps?: number): string | null {
  return formatTimecode(seconds, { showFrames: true, fps });
}

/**
 * Format a clip's start and end as a single range string.
 *
 * Returns `null` unless both ends are usable: a half-open range renders as
 * `01:05 – ` and reads as though the data were truncated.
 *
 * A zero-length range collapses to a single timecode rather than repeating the
 * same value on both sides.
 */
export function formatTimeRange(
  startSeconds: number | null | undefined,
  endSeconds: number | null | undefined,
  options: FormatTimecodeOptions = {}
): string | null {
  const start = formatTimecode(startSeconds, options);
  const end = formatTimecode(endSeconds, options);

  if (start === null || end === null) return null;
  if (start === end) return start;

  return `${start}${RANGE_SEPARATOR}${end}`;
}

/**
 * Format a pair of already-formatted source timecode strings as a range.
 *
 * Used for collection items, which persist `HH:MM:SS:FF` strings rather than
 * seconds. Blank or whitespace-only ends are treated as absent.
 */
export function formatTimecodeRange(
  startTimecode?: string | null,
  endTimecode?: string | null
): string | null {
  const start = startTimecode?.trim();
  const end = endTimecode?.trim();

  if (!start || !end) return null;
  if (start === end) return start;

  return `${start}${RANGE_SEPARATOR}${end}`;
}

/**
 * Format an elapsed duration in seconds as a compact human-readable string:
 * `6s`, `1m 05s`, `1h 02m`.
 *
 * Distinct from `formatTimecode`: a duration answers "how long" and reads badly
 * as a clock (`00:06` for six seconds), whereas a timecode answers "when".
 */
export function formatDuration(seconds: number | null | undefined): string | null {
  if (!isValidTime(seconds)) return null;

  const total = Math.round(seconds);
  if (total < 60) return `${total}s`;

  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;

  // Past an hour the seconds are below the noise floor for a duration label.
  if (hours > 0) return `${hours}h ${pad(minutes)}m`;
  return `${minutes}m ${pad(secs)}s`;
}

/**
 * Parse a timecode string into seconds.
 *
 * Accepts, in order of specificity:
 *   `HH:MM:SS:FF` / `HH:MM:SS;FF`  (frames, converted using `fps`)
 *   `HH:MM:SS.mmm`                 (fractional seconds)
 *   `HH:MM:SS`
 *   `MM:SS.mmm`
 *   `MM:SS`
 *   `SS.mmm` / `SS`                (bare seconds)
 *
 * Returns `null` when nothing matches, so callers can reject the input instead
 * of silently storing a `0`.
 */
export function parseTimecode(timecode: string | null | undefined, fps?: number): number | null {
  if (typeof timecode !== "string") return null;

  const trimmed = timecode.trim();
  if (!trimmed) return null;

  const effectiveFps = resolveFps(fps);

  // HH:MM:SS:FF / HH:MM:SS;FF
  const smpte = trimmed.match(/^(\d{1,2}):(\d{1,2}):(\d{1,2})[:;](\d{1,2})$/);
  if (smpte) {
    const [, h, m, s, f] = smpte;
    const frames = Number(f);
    // A frame index at or beyond the frame rate is not representable; reject
    // rather than rolling it into the next second, which would silently move
    // the marker.
    if (frames >= Math.ceil(effectiveFps)) return null;
    return Number(h) * 3600 + Number(m) * 60 + Number(s) + frames / effectiveFps;
  }

  // HH:MM:SS(.mmm)
  const hms = trimmed.match(/^(\d{1,2}):(\d{1,2}):(\d{1,2}(?:\.\d+)?)$/);
  if (hms) {
    const [, h, m, s] = hms;
    return Number(h) * 3600 + Number(m) * 60 + Number(s);
  }

  // MM:SS(.mmm)
  const ms = trimmed.match(/^(\d{1,3}):(\d{1,2}(?:\.\d+)?)$/);
  if (ms) {
    const [, m, s] = ms;
    return Number(m) * 60 + Number(s);
  }

  // Bare seconds
  const bare = trimmed.match(/^(\d+(?:\.\d+)?)$/);
  if (bare) return Number(bare[1]);

  return null;
}

/**
 * Extract an asset's frame rate from its embedded metadata.
 *
 * Frame rate reaches the UI in three shapes depending on the probe that wrote
 * it: a number, a decimal string ("29.97"), or an ffprobe rational
 * ("30000/1001"). All three are handled. Returns `undefined` rather than a
 * default so callers can distinguish "unknown" from "known to be 25".
 */
export function getAssetFrameRate(asset: unknown): number | undefined {
  const metadata = (asset as any)?.Metadata?.EmbeddedMetadata;
  if (!metadata) return undefined;

  const video = Array.isArray(metadata.video) ? metadata.video[0] : metadata.video;

  const candidates = [
    video?.FrameRate,
    video?.r_frame_rate,
    metadata.general?.FrameRate,
    metadata.general?.r_frame_rate,
  ];

  for (const candidate of candidates) {
    const parsed = parseFrameRate(candidate);
    if (parsed !== undefined) return parsed;
  }

  return undefined;
}

/**
 * Coerce a frame rate value into a positive number.
 *
 * Handles plain numbers, decimal strings, and ffprobe rationals such as
 * "30000/1001". Exported for callers that already hold a raw metadata value.
 */
export function parseFrameRate(value: unknown): number | undefined {
  if (typeof value === "number") {
    return Number.isFinite(value) && value > 0 ? value : undefined;
  }

  if (typeof value !== "string") return undefined;

  const trimmed = value.trim();
  if (!trimmed) return undefined;

  // ffprobe rational form, e.g. "30000/1001".
  const rational = trimmed.match(/^(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/);
  if (rational) {
    const numerator = Number(rational[1]);
    const denominator = Number(rational[2]);
    if (denominator > 0 && Number.isFinite(numerator / denominator)) {
      const fps = numerator / denominator;
      return fps > 0 ? fps : undefined;
    }
    return undefined;
  }

  const parsed = Number.parseFloat(trimmed);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

/**
 * Convert seconds to the `HH:MM:SS:FF` form the collections and download APIs
 * accept.
 *
 * Distinct from `formatSmpte`: this is a wire format, not a display string, so
 * it never returns `null` — an unusable input clamps to `00:00:00:00` because
 * the API contract has no representation for "unknown".
 */
export function secondsToApiTimecode(seconds: number, fps?: number): string {
  const safe = isValidTime(seconds) ? seconds : 0;
  return formatSmpte(safe, fps) ?? "00:00:00:00";
}
