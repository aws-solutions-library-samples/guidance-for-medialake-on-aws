/**
 * Preservation Property Tests — Property 2: Non-Sort Behavior Unchanged
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**
 *
 * These tests capture the baseline behavior of AssetCard's player lifecycle
 * for all NON-SORT interactions on the UNFIXED code. They must PASS on the
 * current (unfixed) code to establish a preservation baseline.
 *
 * Covered behaviors:
 * - Initial render correctly initializes OmakasePlayer (3.1)
 * - Playback controls work without sort changes (3.2)
 * - IntersectionObserver lazy loading initializes players on visibility (3.5)
 * - Changing thumbnailScale updates object-fit without reloading (3.6)
 * - Unmounting properly destroys the OmakasePlayer instance (3.7)
 *
 * Approach: We reuse the same minimal VideoCard component pattern from the
 * bug exploration test, exercising only non-sort paths.
 */

import { describe, it, expect, beforeEach } from "vitest";
import React, { useEffect, useRef, useId, useState, useCallback } from "react";
import { render, act } from "@testing-library/react";
import * as fc from "fast-check";

// ---------------------------------------------------------------------------
// Mock OmakasePlayer — same pattern as bug exploration test
// ---------------------------------------------------------------------------

let constructorCalls: string[] = [];
let destroyCalls: string[] = [];

class MockOmakasePlayer {
  public domElement: HTMLDivElement;
  public destroyed = false;
  public containerId: string;
  public videoElement: HTMLVideoElement;

  constructor(opts: { playerHTMLElementId: string }) {
    this.containerId = opts.playerHTMLElementId;
    const container = document.getElementById(opts.playerHTMLElementId);
    if (!container) throw new Error(`Container #${opts.playerHTMLElementId} not found`);

    this.domElement = document.createElement("div");
    this.domElement.className = "omakase-player-root";
    this.domElement.setAttribute("data-player-id", opts.playerHTMLElementId);

    this.videoElement = document.createElement("video");
    this.domElement.appendChild(this.videoElement);

    container.appendChild(this.domElement);
    constructorCalls.push(opts.playerHTMLElementId);
  }

  destroy() {
    this.destroyed = true;
    destroyCalls.push(this.containerId);
    if (this.domElement.parentNode) {
      this.domElement.remove();
    }
  }
}

// ---------------------------------------------------------------------------
// VideoCard — mirrors AssetCard.tsx player lifecycle (non-sort paths only)
// ---------------------------------------------------------------------------

function VideoCard({
  assetId,
  name,
  isVisible: externalVisible,
  thumbnailScale = "fill",
}: {
  assetId: string;
  name: string;
  isVisible?: boolean;
  thumbnailScale?: "fit" | "fill";
}) {
  const reactId = useId();
  const instanceSuffix = reactId.replace(/:/g, "-");
  const sanitizedId = assetId.replace(/[^a-zA-Z0-9_-]/g, "-");
  const playerId = `omakase-player-${sanitizedId}-${instanceSuffix}`;

  const playerInitializedRef = useRef(false);
  const omakasePlayerRef = useRef<MockOmakasePlayer | null>(null);
  const isMountedRef = useRef(true);

  // Lazy loading — controlled externally for testing
  const [isVisible, setIsVisible] = useState(externalVisible ?? false);

  useEffect(() => {
    if (externalVisible !== undefined) setIsVisible(externalVisible);
  }, [externalVisible]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Mirrors AssetCard.tsx initialization useEffect (line ~222)
  useEffect(() => {
    const playerDiv = document.getElementById(playerId);

    // Stale-player detection (lines ~229-241 of AssetCard.tsx)
    if (playerInitializedRef.current && playerDiv && playerDiv.children.length === 0) {
      if (omakasePlayerRef.current) {
        try {
          omakasePlayerRef.current.destroy();
        } catch (_e) {
          /* noop */
        }
      }
      omakasePlayerRef.current = null;
      playerInitializedRef.current = false;
    }

    // Initialize if visible and not already done
    if (!playerInitializedRef.current && playerDiv && isVisible) {
      try {
        const player = new MockOmakasePlayer({ playerHTMLElementId: playerId });
        omakasePlayerRef.current = player;
        playerInitializedRef.current = true;
      } catch (_e) {
        /* init failed */
      }
    }

    // Cleanup — only on true unmount
    return () => {
      if (omakasePlayerRef.current && !isMountedRef.current) {
        omakasePlayerRef.current.destroy();
        omakasePlayerRef.current = null;
        playerInitializedRef.current = false;
      }
    };
  }, [assetId, playerId, isVisible]);

  // Mirrors thumbnailScale effect (line ~618 of AssetCard.tsx)
  useEffect(() => {
    if (omakasePlayerRef.current && playerInitializedRef.current) {
      try {
        const videoElement = omakasePlayerRef.current.videoElement;
        if (videoElement) {
          const objectFitValue = thumbnailScale === "fit" ? "contain" : "cover";
          videoElement.style.objectFit = objectFitValue;
        }
      } catch (_e) {
        /* noop */
      }
    }
  }, [thumbnailScale, assetId, playerId]);

  return (
    <div data-testid={`card-${assetId}`}>
      <div
        id={playerId}
        data-testid={`player-container-${assetId}`}
        style={{ width: "100%", height: "200px" }}
      />
      <span>{name}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Wrapper for controlling visibility (lazy loading simulation)
// ---------------------------------------------------------------------------

function LazyVideoCard({
  assetId,
  name,
  initiallyVisible = false,
}: {
  assetId: string;
  name: string;
  initiallyVisible?: boolean;
}) {
  const [visible, setVisible] = useState(initiallyVisible);
  return (
    <div>
      <VideoCard assetId={assetId} name={name} isVisible={visible} />
      <button data-testid={`show-${assetId}`} onClick={() => setVisible(true)}>
        Show
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Wrapper for controlling thumbnailScale
// ---------------------------------------------------------------------------

function ScalableVideoCard({ assetId, name }: { assetId: string; name: string }) {
  const [scale, setScale] = useState<"fit" | "fill">("fill");
  return (
    <div>
      <VideoCard assetId={assetId} name={name} isVisible={true} thumbnailScale={scale} />
      <button
        data-testid={`toggle-scale-${assetId}`}
        onClick={() => setScale((s) => (s === "fit" ? "fill" : "fit"))}
      >
        Toggle
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Property-based preservation tests
// ---------------------------------------------------------------------------

describe("Preservation Property Tests — Property 2: Non-Sort Behavior Unchanged", () => {
  beforeEach(() => {
    constructorCalls = [];
    destroyCalls = [];
  });

  // Arbitraries
  const assetIdArb = fc.uuid();
  const nameArb = fc
    .array(fc.constantFrom("a", "b", "c", "d", "e", "f", "g", "h"), {
      minLength: 2,
      maxLength: 6,
    })
    .map((chars) => chars.join(""));

  /**
   * Property 2a: Initial render correctly initializes OmakasePlayer
   *
   * For any render where no sort change occurs, playerInitializedRef
   * transitions from false to true exactly once, and the player DOM is
   * correctly injected into the container.
   *
   * **Validates: Requirements 3.1**
   */
  it("initial render initializes player exactly once with DOM correctly injected", () => {
    fc.assert(
      fc.property(assetIdArb, nameArb, (assetId, name) => {
        constructorCalls = [];
        destroyCalls = [];

        const { container: rootEl, unmount } = render(
          <VideoCard assetId={assetId} name={name} isVisible={true} />
        );

        // Player should be initialized exactly once
        expect(constructorCalls.length).toBe(1);

        // Player DOM should be injected into the container
        const containerDiv = rootEl.querySelector(
          `[data-testid="player-container-${assetId}"]`
        ) as HTMLElement;
        expect(containerDiv).not.toBeNull();

        const playerRoot = containerDiv!.querySelector(".omakase-player-root");
        expect(playerRoot).not.toBeNull();
        expect(containerDiv!.contains(playerRoot)).toBe(true);

        // Player should have a video element
        const videoEl = playerRoot!.querySelector("video");
        expect(videoEl).not.toBeNull();

        // No destroy calls during normal init
        expect(destroyCalls.length).toBe(0);

        unmount();
      }),
      { numRuns: 20 }
    );
  });

  /**
   * Property 2b: Lazy loading — player initializes only when visible
   *
   * For any video card that starts hidden, the player is NOT initialized
   * until visibility is triggered. Once visible, initialization happens
   * exactly once.
   *
   * **Validates: Requirements 3.5**
   */
  it("lazy loading: player initializes only after becoming visible", () => {
    fc.assert(
      fc.property(assetIdArb, nameArb, (assetId, name) => {
        constructorCalls = [];
        destroyCalls = [];

        const { container: rootEl, unmount } = render(
          <LazyVideoCard assetId={assetId} name={name} initiallyVisible={false} />
        );

        // Player should NOT be initialized while hidden
        expect(constructorCalls.length).toBe(0);

        const containerDiv = rootEl.querySelector(
          `[data-testid="player-container-${assetId}"]`
        ) as HTMLElement;
        expect(containerDiv).not.toBeNull();
        expect(containerDiv!.querySelector(".omakase-player-root")).toBeNull();

        // Simulate becoming visible (IntersectionObserver fires)
        const showBtn = rootEl.querySelector(`[data-testid="show-${assetId}"]`) as HTMLElement;
        act(() => {
          showBtn.click();
        });

        // Now player should be initialized exactly once
        expect(constructorCalls.length).toBe(1);

        const playerRoot = containerDiv!.querySelector(".omakase-player-root");
        expect(playerRoot).not.toBeNull();
        expect(containerDiv!.contains(playerRoot)).toBe(true);

        unmount();
      }),
      { numRuns: 20 }
    );
  });

  /**
   * Property 2c: Thumbnail scale changes update object-fit without reloading
   *
   * For any video card with an initialized player, changing thumbnailScale
   * updates the video element's object-fit style without destroying or
   * re-initializing the player.
   *
   * **Validates: Requirements 3.6**
   */
  it("thumbnailScale change updates object-fit without player reload", () => {
    fc.assert(
      fc.property(assetIdArb, nameArb, (assetId, name) => {
        constructorCalls = [];
        destroyCalls = [];

        const { container: rootEl, unmount } = render(
          <ScalableVideoCard assetId={assetId} name={name} />
        );

        // Player initialized once with default "fill"
        expect(constructorCalls.length).toBe(1);

        const containerDiv = rootEl.querySelector(
          `[data-testid="player-container-${assetId}"]`
        ) as HTMLElement;
        const videoEl = containerDiv!.querySelector("video") as HTMLVideoElement;
        expect(videoEl).not.toBeNull();

        // Default should be "cover" (fill mode)
        expect(videoEl.style.objectFit).toBe("cover");

        // Toggle to "fit"
        const toggleBtn = rootEl.querySelector(
          `[data-testid="toggle-scale-${assetId}"]`
        ) as HTMLElement;
        act(() => {
          toggleBtn.click();
        });

        // object-fit should now be "contain"
        expect(videoEl.style.objectFit).toBe("contain");

        // No re-initialization or destruction
        expect(constructorCalls.length).toBe(1);
        expect(destroyCalls.length).toBe(0);

        // Toggle back to "fill"
        act(() => {
          toggleBtn.click();
        });

        expect(videoEl.style.objectFit).toBe("cover");
        expect(constructorCalls.length).toBe(1);
        expect(destroyCalls.length).toBe(0);

        unmount();
      }),
      { numRuns: 20 }
    );
  });

  /**
   * Property 2d: Unmount properly destroys OmakasePlayer exactly once
   *
   * For any unmount event, OmakasePlayer.destroy() is called exactly once,
   * cleaning up resources properly.
   *
   * **Validates: Requirements 3.7**
   */
  it("unmount destroys player exactly once", () => {
    fc.assert(
      fc.property(assetIdArb, nameArb, (assetId, name) => {
        constructorCalls = [];
        destroyCalls = [];

        const { unmount } = render(<VideoCard assetId={assetId} name={name} isVisible={true} />);

        expect(constructorCalls.length).toBe(1);
        expect(destroyCalls.length).toBe(0);

        // Unmount the component (simulates navigating away)
        unmount();

        // destroy() should be called exactly once
        expect(destroyCalls.length).toBe(1);
      }),
      { numRuns: 20 }
    );
  });

  /**
   * Property 2e: Re-render without sort change preserves player
   *
   * For any re-render where no sort change occurs (e.g., parent re-renders
   * with same props), the player is NOT destroyed or re-initialized.
   * This covers playback control interactions that trigger re-renders.
   *
   * **Validates: Requirements 3.2**
   */
  it("re-render without sort change preserves player instance", () => {
    fc.assert(
      fc.property(assetIdArb, nameArb, (assetId, name) => {
        constructorCalls = [];
        destroyCalls = [];

        const {
          rerender,
          container: rootEl,
          unmount,
        } = render(<VideoCard assetId={assetId} name={name} isVisible={true} />);

        expect(constructorCalls.length).toBe(1);

        // Re-render with same props (simulates parent re-render during playback)
        act(() => {
          rerender(<VideoCard assetId={assetId} name={name} isVisible={true} />);
        });

        // Player should NOT be re-initialized
        expect(constructorCalls.length).toBe(1);
        expect(destroyCalls.length).toBe(0);

        // Player DOM should still be connected
        const containerDiv = rootEl.querySelector(
          `[data-testid="player-container-${assetId}"]`
        ) as HTMLElement;
        const playerRoot = containerDiv!.querySelector(".omakase-player-root");
        expect(playerRoot).not.toBeNull();
        expect(containerDiv!.contains(playerRoot)).toBe(true);

        // Re-render again (multiple re-renders during playback interactions)
        act(() => {
          rerender(<VideoCard assetId={assetId} name={name} isVisible={true} />);
        });

        expect(constructorCalls.length).toBe(1);
        expect(destroyCalls.length).toBe(0);

        unmount();
      }),
      { numRuns: 20 }
    );
  });
});
