/**
 * One-off repair for sessions carrying an oversized notification key.
 *
 * `medialake_unseen_notifications` used to be keyed by the notification's
 * per-session `crypto.randomUUID()`, which is minted fresh every time a
 * notification is created — and the job sync re-creates one on every cold load
 * for any job whose notification is missing from state. Nothing pruned the
 * stored array, so it grew by one uuid per job per load until `setItem` threw
 * `QuotaExceededError` out of an effect at the app root, taking every route down
 * with "Something went wrong". Observed in production at 1.7 MB.
 *
 * The write path no longer grows (see `markAsUnseen`), but that only fixes what
 * gets written from now on. An affected profile still holds the old value, and
 * the write path reads it, adds to it and writes it back — so without this the
 * fix rescues nobody who already has the bug, and they cannot recover
 * themselves: the app dies before it renders, and share pages have no
 * notification bell to clear it from.
 */

/**
 * Keys holding derived notification bookkeeping. Every entry is keyed by a
 * backend job id or a per-session uuid, so nothing here is authoritative — it is
 * all rebuilt from the job list on the next sync, which makes it safe to drop.
 */
const DISPOSABLE_KEYS = [
  "medialake_unseen_notifications",
  "medialake_seen_job_notifications",
  "medialake_dismissed_jobs",
  "medialake_notifications",
] as const;

/**
 * Past this many UTF-16 characters a notification key is the result of unbounded
 * growth rather than real state: the sets hold ~39-character entries, so 256k
 * characters is on the order of six thousand of them where a few dozen is the
 * working maximum.
 */
const DISPOSABLE_KEY_MAX_CHARS = 256 * 1024;

/** Drop any notification key that has grown past its useful size. Runs before React mounts. */
export function pruneOversizedNotificationStorage(): void {
  for (const key of DISPOSABLE_KEYS) {
    try {
      const value = localStorage.getItem(key);
      if (value && value.length > DISPOSABLE_KEY_MAX_CHARS) {
        localStorage.removeItem(key);
        console.warn(
          `Removed "${key}" (${Math.round(value.length / 1024)} KB): ` +
            `notification bookkeeping had grown past its useful size and is rebuilt on the next sync.`
        );
      }
    } catch {
      // Storage unavailable (private mode, blocked cookies) — nothing to prune.
    }
  }
}
