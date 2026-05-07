/**
 * playerCache — module-level LRU cache for OmakasePlayer instances.
 *
 * Keeps up to MAX_PARKED players alive (paused, DOM parked offscreen)
 * so that scrolling back to a card or navigating back to a page
 * can re-attach instantly without re-constructing the player or
 * re-fetching the video stream.
 *
 * Active players (currently attached to a visible card) are NOT counted
 * toward the cache limit — only parked (offscreen) players are.
 *
 * Video src is preserved on park so buffered data survives.
 * The LRU eviction destroys the oldest parked player when the cap is hit.
 */
import type { OmakasePlayer } from "@byomakase/omakase-player";

export interface CachedEntry {
  player: OmakasePlayer;
  proxyUrl: string;
  wrapper: HTMLElement;
  lastAccessed: number;
}

const MAX_PARKED = 12;

const parkedPlayers = new Map<string, CachedEntry>();

// Off-screen host — lives outside React's tree entirely.
// Parked player DOM subtrees are moved here so they stay alive
// but invisible and non-interactive.
let offscreenHost: HTMLDivElement | null = null;

function getOffscreenHost(): HTMLDivElement {
  if (!offscreenHost) {
    offscreenHost = document.createElement("div");
    offscreenHost.id = "omakase-player-cache-host";
    offscreenHost.style.cssText = [
      "position:fixed",
      "left:-9999px",
      "top:-9999px",
      "width:0",
      "height:0",
      "overflow:hidden",
      "visibility:hidden",
      "pointer-events:none",
    ].join(";");
    document.body.appendChild(offscreenHost);
  }
  return offscreenHost;
}

/**
 * Retrieve a cached player without removing it from the cache.
 * Updates lastAccessed so LRU eviction knows this entry is fresh.
 */
export function getCached(assetId: string): CachedEntry | undefined {
  const entry = parkedPlayers.get(assetId);
  if (entry) {
    entry.lastAccessed = Date.now();
  }
  return entry;
}

/**
 * Park a player: pause it, move its DOM subtree offscreen, and store it.
 * Video src is intentionally preserved so buffered data survives.
 */
export function parkPlayer(
  assetId: string,
  player: OmakasePlayer,
  proxyUrl: string,
  wrapper: HTMLElement
): void {
  // Pause playback but keep the src so buffered data is retained
  try {
    const videoEl = player.video?.getHTMLVideoElement();
    if (videoEl) {
      videoEl.pause();
    }
  } catch {
    /* ok */
  }

  getOffscreenHost().appendChild(wrapper);
  parkedPlayers.set(assetId, {
    player,
    proxyUrl,
    wrapper,
    lastAccessed: Date.now(),
  });
  evictIfNeeded();
}

/**
 * Unpark a player: remove it from the cache and return it.
 * The caller is responsible for re-attaching the wrapper to the DOM.
 */
export function unpark(assetId: string): CachedEntry | undefined {
  const entry = parkedPlayers.get(assetId);
  if (entry) {
    parkedPlayers.delete(assetId);
  }
  return entry;
}

/**
 * Unpark and destroy a stale cached entry (e.g. proxy URL changed).
 * Releases all resources — the caller should proceed with a fresh init.
 */
export function evictStale(assetId: string): void {
  const entry = parkedPlayers.get(assetId);
  if (!entry) return;
  parkedPlayers.delete(assetId);

  try {
    const videoEl = entry.player.video?.getHTMLVideoElement();
    if (videoEl) {
      videoEl.pause();
      videoEl.removeAttribute("src");
      videoEl.load();
    }
  } catch {
    /* ok */
  }

  try {
    entry.player.destroy();
  } catch {
    /* ok */
  }

  try {
    entry.wrapper.remove();
  } catch {
    /* ok */
  }
}

/** Destroy a single cached entry, releasing all resources. */
function destroyEntry(assetId: string): void {
  const entry = parkedPlayers.get(assetId);
  if (!entry) return;

  try {
    const videoEl = entry.player.video?.getHTMLVideoElement();
    if (videoEl) {
      videoEl.pause();
      videoEl.removeAttribute("src");
      videoEl.load();
    }
  } catch {
    /* ok */
  }

  try {
    entry.player.destroy();
  } catch {
    /* ok */
  }

  try {
    entry.wrapper.remove();
  } catch {
    /* ok */
  }

  parkedPlayers.delete(assetId);
}

/** Evict the least-recently-used entry when over the cap. */
function evictIfNeeded(): void {
  while (parkedPlayers.size > MAX_PARKED) {
    let oldestKey: string | null = null;
    let oldestTime = Infinity;
    for (const [key, entry] of parkedPlayers) {
      if (entry.lastAccessed < oldestTime) {
        oldestTime = entry.lastAccessed;
        oldestKey = key;
      }
    }
    if (oldestKey) {
      destroyEntry(oldestKey);
    } else {
      break;
    }
  }
}

/** Destroy all parked players. Call on app teardown if needed. */
export function destroyAll(): void {
  for (const key of [...parkedPlayers.keys()]) {
    destroyEntry(key);
  }
}

/** Current number of parked players (useful for debugging). */
export function parkedCount(): number {
  return parkedPlayers.size;
}
