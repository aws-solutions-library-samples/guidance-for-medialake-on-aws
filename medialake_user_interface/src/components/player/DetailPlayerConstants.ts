export const DETAIL_PLAYER_CONTAINER_ID_PREFIX = "omakase-detail-player";

/**
 * Ids for the two marker bars the detail player registers on its chroming.
 *
 * Omakase addresses marker bars by a caller-supplied id
 * (`ChromingMarkerBarConfig.id`), which is also how they are looked up with
 * `chroming.getMarkerBar(id)` and removed with `deleteMarkerBar(id)`. Keeping the
 * ids here means the player hook and anything inspecting the bars agree on them.
 */
export const MARKER_BAR_ID = {
  /** User-authored markers — editable. */
  USER: "medialake-user-markers",
  /** Semantic/AI clip matches — read-only. */
  CLIP: "medialake-clip-markers",
} as const;

/** Human-readable labels for the two marker tracks, shown by Omakase surfaces. */
export const MARKER_TRACK_LABEL = {
  USER: "Markers",
  CLIP: "Clips",
} as const;
