/**
 * Clip deep links — carrying "which clip did I click" in the URL.
 *
 * ## The problem
 *
 * Clicking a semantic search result used to navigate to the asset detail page
 * with the search term and the clip *only in router state*. Router state does not
 * survive a reload, a copied link, or a restored tab, so a refreshed detail page
 * lost both: the breadcrumb went back to a bare asset name, and the playhead sat
 * at 00:00 with no indication which moment the user had picked.
 *
 * Putting both in the query string fixes the part that can be fixed without a
 * server round trip. `?q=<term>&t=<seconds>` is enough to restore the breadcrumb
 * and seek to the clicked moment on a cold load.
 *
 * ## What deliberately does *not* survive a reload
 *
 * The semantic markers themselves. Their scores are relative to the search query,
 * and the search API has no filter that scopes a semantic query to a single
 * asset — so the detail page cannot re-derive the clip set for one asset on its
 * own. Reload therefore restores the *position* and the search term, not the 38
 * scored clip markers. Recovering those needs either a scope-to-asset search
 * filter or the markers API; both are out of scope here.
 *
 * `t` is seconds rather than a timecode: it needs no frame rate to interpret, so
 * it stays correct on a cold load that happens before asset metadata (and with it
 * the real frame rate) has arrived.
 */
import { getAssetFrameRate, parseTimecode } from "@/utils/timecode";

/** Query parameter names. `t` follows the familiar `?t=` seek convention. */
export const CLIP_DEEP_LINK_PARAM = {
  searchTerm: "q",
  startTime: "t",
} as const;

export interface ClipDeepLink {
  /** The search that produced the result, for the breadcrumb and marker labels. */
  searchTerm?: string;
  /** Seconds into the asset of the clicked clip. */
  startTime?: number;
}

/**
 * The start time, in seconds, of the single clip a search result represents.
 *
 * Returns undefined when the result is not a single clip — in grouped ("Full")
 * search mode a card stands for the whole asset and carries every match, so
 * there is no one clicked moment to link to.
 *
 * Shapes are read in order of trustworthiness: an explicit number first, then the
 * `_seconds` field the search API actually returns, then a parsed timecode. The
 * timecode path needs the asset's frame rate, which is why `asset` is consulted
 * for it rather than assuming a default.
 */
export function clipStartSeconds(asset: unknown): number | undefined {
  if (!asset || typeof asset !== "object") return undefined;

  const record = asset as Record<string, any>;
  const clips = record.clips;

  // `clipData` is set by transformResultsToClipMode for per-clip cards. Otherwise
  // accept a clips array of exactly one, which is the same thing expressed by the
  // API payload. More than one clip means "whole asset", not a clicked clip.
  const clip =
    record.clipData ?? (Array.isArray(clips) && clips.length === 1 ? clips[0] : undefined);
  if (!clip || typeof clip !== "object") return undefined;

  if (typeof clip.start === "number" && Number.isFinite(clip.start)) return clip.start;
  if (typeof clip.start_seconds === "number" && Number.isFinite(clip.start_seconds)) {
    return clip.start_seconds;
  }

  const timecode = clip.start_timecode ?? clip.start_time;
  if (typeof timecode === "string") {
    const parsed = parseTimecode(timecode, getAssetFrameRate(asset));
    if (parsed !== null) return parsed;
  }

  return undefined;
}

/**
 * Build the query string for a detail-page link, including the leading `?`.
 *
 * Returns "" when there is nothing to carry, so callers can append it
 * unconditionally without producing a trailing `?`.
 */
export function buildClipDeepLinkSearch(link: ClipDeepLink): string {
  const params = new URLSearchParams();

  const term = link.searchTerm?.trim();
  if (term) params.set(CLIP_DEEP_LINK_PARAM.searchTerm, term);

  // 0 is a legitimate start time, so test finiteness rather than truthiness.
  // Negative values are dropped: they cannot name a position in the media.
  if (
    typeof link.startTime === "number" &&
    Number.isFinite(link.startTime) &&
    link.startTime >= 0
  ) {
    // Millisecond precision is plenty and keeps the URL readable; clip
    // boundaries arrive as whole seconds in practice.
    params.set(CLIP_DEEP_LINK_PARAM.startTime, String(Math.round(link.startTime * 1000) / 1000));
  }

  const search = params.toString();
  return search ? `?${search}` : "";
}

/**
 * Read a deep link back out of a location's search string.
 *
 * `searchTerm` also accepts the legacy `searchTerm` key so links shared before
 * `q` was settled on keep working.
 */
export function readClipDeepLink(search: string): ClipDeepLink {
  const params = new URLSearchParams(search);

  const term = params.get(CLIP_DEEP_LINK_PARAM.searchTerm) || params.get("searchTerm") || "";

  const rawStart = params.get(CLIP_DEEP_LINK_PARAM.startTime);
  let startTime: number | undefined;
  if (rawStart !== null && rawStart.trim() !== "") {
    // `Number("")` is 0, hence the blank guard above — an empty `t=` must not
    // seek to the head of the timeline.
    const parsed = Number(rawStart);
    if (Number.isFinite(parsed) && parsed >= 0) startTime = parsed;
  }

  return {
    ...(term ? { searchTerm: term } : {}),
    ...(startTime !== undefined ? { startTime } : {}),
  };
}
