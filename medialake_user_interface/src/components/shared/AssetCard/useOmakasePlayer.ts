/**
 * useOmakasePlayer — manages the full Omakase video/audio player lifecycle.
 *
 * Loading strategy:
 * - Auto-loads when the card enters the viewport (no hover required)
 * - Loads in visual order: top-to-bottom, left-to-right via a priority queue
 * - Max concurrent loads controlled by serialized init chain
 * - Async and non-blocking — queue waits via microtasks, never blocks the main thread
 * - Parks player to an LRU cache when card scrolls out of viewport (preserves video buffer)
 * - Re-attaches cached player instantly when card scrolls back in
 * - LRU cache survives page navigation within the SPA — max 12 parked players
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { OmakasePlayer, PlayerChromingTheme, StampThemeScale } from "@byomakase/omakase-player";
import { addMarkersToPlayer, type ClipData } from "./markerHelpers";
import { parkPlayer, unpark, getCached, evictStale, type CachedEntry } from "./playerCache";

// Use a generic unsubscribe interface to avoid rxjs version conflicts
interface Unsubscribable {
  unsubscribe(): void;
}

// Yield to the browser so it can paint, process input, and update cursors.
function yieldToMain(): Promise<void> {
  if ("scheduler" in window && typeof (window as any).scheduler?.yield === "function") {
    return (window as any).scheduler.yield();
  }
  return new Promise((resolve) => setTimeout(resolve, 0));
}

// ─── Priority Init Queue ───
// OmakasePlayer constructors are heavy (Konva canvas + layers + event wiring).
// This queue ensures only one constructor runs per browser task, and processes
// cards in visual order: top-to-bottom, left-to-right.
// loadVideo() calls (network I/O) still run fully in parallel.

interface QueueEntry {
  id: string;
  top: number;
  left: number;
  resolve: () => void;
  reject: (reason?: unknown) => void;
}

let queue: QueueEntry[] = [];
let processing = false;

async function processQueue(): Promise<void> {
  if (processing) return;
  processing = true;
  try {
    while (queue.length > 0) {
      // Sort by visual position: top first, then left
      queue.sort((a, b) => a.top - b.top || a.left - b.left);
      const entry = queue.shift()!;
      await yieldToMain();
      entry.resolve();
    }
  } finally {
    processing = false;
    // If new entries arrived while we were finishing, restart
    if (queue.length > 0) {
      processQueue();
    }
  }
}

function enqueueInit(id: string, element: HTMLElement): Promise<void> {
  // Remove any existing entry for this id (reject it so the old promise settles)
  dequeueInit(id);

  const rect = element.getBoundingClientRect();
  return new Promise<void>((resolve, reject) => {
    queue.push({ id, top: rect.top, left: rect.left, resolve, reject });
    processQueue();
  });
}

function dequeueInit(id: string): void {
  const removed = queue.filter((e) => e.id === id);
  queue = queue.filter((e) => e.id !== id);
  // Reject removed entries so their promises don't hang forever
  for (const entry of removed) {
    entry.reject(new Error("dequeued"));
  }
}

function scheduleMarkerUpdate(
  player: OmakasePlayer,
  id: string,
  clips: ClipData[],
  isSemantic: boolean,
  confidenceThreshold: number,
  timeoutMs: number,
  onComplete: (ids: string[]) => void
): () => void {
  let idleId: number | null = null;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const callback = () => {
    try {
      onComplete(addMarkersToPlayer(player, id, clips, isSemantic, confidenceThreshold));
    } catch (e) {
      console.error("Failed to add markers:", e);
    }
  };

  if ("requestIdleCallback" in window) {
    idleId = requestIdleCallback(callback, { timeout: timeoutMs });
  } else {
    timeoutId = setTimeout(callback, 50);
  }

  return () => {
    if (idleId !== null && "cancelIdleCallback" in window) cancelIdleCallback(idleId);
    if (timeoutId !== null) clearTimeout(timeoutId);
  };
}

interface UseOmakasePlayerOptions {
  id: string;
  instanceSuffix: string;
  assetType?: string;
  proxyUrl?: string;
  thumbnailUrl?: string;
  thumbnailScale: "fit" | "fill";
  clips?: ClipData[];
  isSemantic: boolean;
  confidenceThreshold: number;
  variant: "compact" | "full";
  cardContainerRef: React.RefObject<HTMLDivElement | null>;
}

export function useOmakasePlayer({
  id,
  instanceSuffix,
  assetType,
  proxyUrl,
  thumbnailUrl,
  thumbnailScale,
  clips,
  isSemantic,
  confidenceThreshold,
  // variant is part of the options interface but unused in this hook
  cardContainerRef,
}: UseOmakasePlayerOptions) {
  const isMediaAsset = assetType === "Video" || assetType === "Audio";
  const sanitizedId = id.replace(/[^a-zA-Z0-9_-]/g, "-");
  const playerId = `omakase-player-${sanitizedId}-${instanceSuffix}`;

  const [isInViewport, setIsInViewport] = useState(false);
  const [videoLoadError, setVideoLoadError] = useState(false);
  const [isPlayerActive, setIsPlayerActive] = useState(false);

  const playerRef = useRef<OmakasePlayer | null>(null);
  const playerInitializedRef = useRef(false);
  const currentProxyUrlRef = useRef<string | undefined>(undefined);
  const playerWrapperRef = useRef<HTMLElement | null>(null);
  const markerIdsRef = useRef<string[]>([]);
  const isMountedRef = useRef(true);
  const loadSubscriptionRef = useRef<Unsubscribable | null>(null);
  const markerCleanupRef = useRef<(() => void) | null>(null);
  const abortedRef = useRef(false);

  // Store clips/semantic in refs so the init effect can read current values
  const clipsRef = useRef(clips);
  clipsRef.current = clips;
  const isSemanticRef = useRef(isSemantic);
  isSemanticRef.current = isSemantic;
  const confidenceRef = useRef(confidenceThreshold);
  confidenceRef.current = confidenceThreshold;

  const getLoadOptions = useCallback(() => {
    if (assetType === "Audio") return { protocol: "audio" as const };
    if (assetType === "Video" && thumbnailUrl) return { poster: thumbnailUrl };
    return undefined;
  }, [assetType, thumbnailUrl]);

  const scheduleMarkers = useCallback(() => {
    markerCleanupRef.current?.();
    if (!playerRef.current) return;
    markerCleanupRef.current = scheduleMarkerUpdate(
      playerRef.current,
      id,
      clipsRef.current || [],
      isSemanticRef.current,
      confidenceRef.current,
      2000,
      (ids) => {
        markerIdsRef.current = ids;
      }
    );
  }, [id]);

  // ─── Park: pause + move DOM offscreen into LRU cache ───
  // Video src is preserved so buffered data survives for instant re-attach.
  const doParkPlayer = useCallback(() => {
    loadSubscriptionRef.current?.unsubscribe();
    loadSubscriptionRef.current = null;

    markerCleanupRef.current?.();
    markerCleanupRef.current = null;

    if (playerRef.current) {
      // Use the tracked wrapper ref — the container div may already be
      // removed from the DOM by React's unmount before this cleanup runs.
      const wrapper = playerWrapperRef.current;

      if (wrapper) {
        parkPlayer(id, playerRef.current, currentProxyUrlRef.current || "", wrapper);
      } else {
        // No wrapper tracked — fall back to full destroy
        try {
          const videoEl = playerRef.current.video?.getHTMLVideoElement();
          if (videoEl) {
            videoEl.pause();
            videoEl.removeAttribute("src");
            videoEl.load();
          }
        } catch {
          /* ok */
        }
        try {
          playerRef.current.destroy();
        } catch {
          /* ok */
        }
      }

      playerRef.current = null;
      playerWrapperRef.current = null;
    }

    playerInitializedRef.current = false;
    currentProxyUrlRef.current = undefined;
    setIsPlayerActive(false);
  }, [id]);

  // ─── Re-attach a cached player into the current container ───
  const reattachCached = useCallback(
    (cached: CachedEntry, container: HTMLElement) => {
      container.appendChild(cached.wrapper);
      playerRef.current = cached.player;
      playerWrapperRef.current = cached.wrapper;
      playerInitializedRef.current = true;
      currentProxyUrlRef.current = cached.proxyUrl;
      setVideoLoadError(false);
      setIsPlayerActive(true);
      scheduleMarkers();
    },
    [scheduleMarkers]
  );

  // Mount/unmount tracking + cleanup
  useEffect(() => {
    isMountedRef.current = true;
    abortedRef.current = false;
    return () => {
      isMountedRef.current = false;
      abortedRef.current = true;
      dequeueInit(id);
      // On true unmount, park instead of destroy so the cache can reuse it
      doParkPlayer();
    };
  }, [doParkPlayer, id]);

  // IntersectionObserver — tracks viewport visibility for auto-load AND cleanup
  useEffect(() => {
    if (!isMediaAsset || !cardContainerRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          setIsInViewport(entry.isIntersecting);
        });
      },
      { rootMargin: "600px 0px", threshold: 0.01 }
    );
    observer.observe(cardContainerRef.current);
    return () => observer.disconnect();
  }, [isMediaAsset, cardContainerRef]);

  // Park player when card scrolls out of viewport (instead of destroying)
  useEffect(() => {
    if (!isInViewport && playerInitializedRef.current) {
      abortedRef.current = true;
      doParkPlayer();
    }
    if (!isInViewport) {
      // Remove from init queue if it was waiting
      dequeueInit(id);
    }
  }, [isInViewport, doParkPlayer, id]);

  // Auto-initialize player when card enters viewport
  // Checks the LRU cache first for instant re-attach, falls back to fresh init
  useEffect(() => {
    if (!isMediaAsset || !proxyUrl || !isInViewport) return;

    const playerDiv = document.getElementById(playerId);

    // Detect stale player (DOM replaced by React virtual list reorder)
    if (playerInitializedRef.current && playerDiv && playerDiv.children.length === 0) {
      doParkPlayer();
    }

    if (!playerInitializedRef.current) {
      abortedRef.current = false;

      // ─── Try cache first: instant re-attach, no constructor, no network ───
      const cached = getCached(id);
      if (cached && cached.proxyUrl === proxyUrl && playerDiv) {
        // Cache hit — unpark and re-attach
        unpark(id);
        reattachCached(cached, playerDiv);
        return;
      }

      // Cache miss or URL changed — evict stale entry if any
      if (cached) {
        evictStale(id);
      }

      // ─── Fresh init ───
      const initPlayer = async () => {
        // Wait in the priority queue — cards are processed in visual order
        // (top-to-bottom, left-to-right) with one constructor per browser task.
        const containerEl = cardContainerRef.current;
        if (!containerEl) return;
        try {
          await enqueueInit(id, containerEl);
        } catch {
          // Dequeued (card left viewport or unmounted) — abort silently
          return;
        }

        if (abortedRef.current || !isMountedRef.current) return;

        // Re-check DOM after yielding
        const div = document.getElementById(playerId);
        if (!div) return;

        // One more cache check — another card may have been evicted
        // and this asset's entry could have appeared while we yielded
        const lateHit = getCached(id);
        if (lateHit && lateHit.proxyUrl === proxyUrl) {
          unpark(id);
          reattachCached(lateHit, div);
          return;
        }
        if (lateHit) {
          evictStale(id);
        }

        try {
          const player = new OmakasePlayer({
            playerHTMLElementId: playerId,
            playerChroming: {
              theme: PlayerChromingTheme.Stamp,
              themeConfig: {
                stampScale: thumbnailScale === "fit" ? StampThemeScale.Fit : StampThemeScale.Fill,
              },
            },
          });

          playerRef.current = player;
          playerInitializedRef.current = true;
          currentProxyUrlRef.current = proxyUrl;

          // Track the wrapper element so doParkPlayer can find it
          // even after React removes the container from the DOM.
          const wrapper = div.querySelector(".omakase-player") as HTMLElement | null;
          playerWrapperRef.current = wrapper;

          setVideoLoadError(false);

          loadSubscriptionRef.current = player.loadVideo(proxyUrl, getLoadOptions()).subscribe({
            next: () => {
              if (!isMountedRef.current) return;
              setIsPlayerActive(true);
              scheduleMarkers();
            },
            error: (error: unknown) => {
              console.error(`Failed to load ${assetType?.toLowerCase()} for asset ${id}:`, error);
              setVideoLoadError(true);
            },
          });
        } catch (error) {
          console.error(
            `Failed to initialize player for ${assetType?.toLowerCase()} asset ${id}:`,
            error
          );
        }
      };

      initPlayer();
    }
    // Proxy URL changed — reload
    else if (
      playerInitializedRef.current &&
      currentProxyUrlRef.current !== proxyUrl &&
      playerRef.current
    ) {
      currentProxyUrlRef.current = proxyUrl;
      loadSubscriptionRef.current?.unsubscribe();
      loadSubscriptionRef.current = playerRef.current
        .loadVideo(proxyUrl, getLoadOptions())
        .subscribe({
          next: () => {
            if (!isMountedRef.current) return;
            setIsPlayerActive(true);
            scheduleMarkers();
          },
          error: (error: unknown) => {
            console.error(`Failed to reload ${assetType?.toLowerCase()} for asset ${id}:`, error);
            setVideoLoadError(true);
          },
        });
    }

    return () => {
      abortedRef.current = true;
    };
  }, [
    assetType,
    proxyUrl,
    id,
    isInViewport,
    instanceSuffix,
    playerId,
    thumbnailScale,
    isMediaAsset,
    getLoadOptions,
    scheduleMarkers,
    doParkPlayer,
    reattachCached,
    cardContainerRef,
  ]);

  // Marker updates when clips or confidence threshold changes
  useEffect(() => {
    if (!isMediaAsset || !playerRef.current || !Array.isArray(clips) || clips.length === 0) return;

    return scheduleMarkerUpdate(
      playerRef.current,
      id,
      clips,
      isSemantic,
      confidenceThreshold,
      1000,
      (ids) => {
        markerIdsRef.current = ids;
      }
    );
  }, [clips, isSemantic, confidenceThreshold, isMediaAsset, id]);

  // ThumbnailScale changes without reload
  useEffect(() => {
    if (!isMediaAsset || !playerRef.current || !playerInitializedRef.current) return;
    try {
      const objectFit = thumbnailScale === "fit" ? "contain" : "cover";
      const videoEl = playerRef.current.video.getHTMLVideoElement();
      if (videoEl) videoEl.style.objectFit = objectFit;
      const container = document.getElementById(playerId);
      container?.querySelectorAll("video").forEach((v) => {
        v.style.objectFit = objectFit;
      });
    } catch {
      /* ok */
    }
  }, [thumbnailScale, isMediaAsset, playerId]);

  return { isInViewport, videoLoadError, playerId, isMediaAsset, isPlayerActive };
}
