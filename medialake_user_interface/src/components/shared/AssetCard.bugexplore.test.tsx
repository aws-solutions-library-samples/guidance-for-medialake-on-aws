/**
 * Bug Condition Exploration Test — Property 1: Fault Condition
 *
 * Player DOM Detaches After Sort Reorder
 *
 * **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
 *
 * This test surfaces counterexamples demonstrating that after a sort-order
 * change, the OmakasePlayer's DOM subtree becomes detached from its
 * React-managed container. The playerInitializedRef guard prevents
 * re-initialization, leaving the player in a broken (black-screen) state.
 *
 * Approach: We extract the exact player lifecycle logic from AssetCard.tsx
 * into a minimal VideoCard component. To faithfully reproduce the DOM
 * detachment that React's reconciliation causes during list reordering,
 * we use a key on the inner container div that changes on sort. This forces
 * React to create a new DOM node for the container, exactly as happens in
 * a real browser when React moves list items.
 *
 * EXPECTED OUTCOME on UNFIXED code: FAIL — proving the bug exists.
 */

import { describe, it, expect, beforeEach } from "vitest";
import React, { useEffect, useRef, useId, useMemo } from "react";
import { render, act } from "@testing-library/react";
import * as fc from "fast-check";

// ---------------------------------------------------------------------------
// Mock OmakasePlayer
// ---------------------------------------------------------------------------

let constructorCalls: string[] = [];
let destroyCalls: string[] = [];

class MockOmakasePlayer {
  public domElement: HTMLDivElement;
  public destroyed = false;
  public containerId: string;

  constructor(opts: { playerHTMLElementId: string }) {
    this.containerId = opts.playerHTMLElementId;
    const container = document.getElementById(opts.playerHTMLElementId);
    if (!container) throw new Error(`Container #${opts.playerHTMLElementId} not found`);

    this.domElement = document.createElement("div");
    this.domElement.className = "omakase-player-root";
    this.domElement.setAttribute("data-player-id", opts.playerHTMLElementId);

    const videoEl = document.createElement("video");
    this.domElement.appendChild(videoEl);

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
// VideoCard — mirrors AssetCard.tsx player lifecycle
// ---------------------------------------------------------------------------

/**
 * Minimal reproduction of AssetCard's player initialization and stale-detection.
 *
 * The `sortGeneration` prop changes when a sort occurs. We use it as a key on
 * the inner container div, which forces React to create a new DOM node — this
 * simulates the container replacement that happens during real browser
 * reconciliation when list items are reordered.
 */
function VideoCard({
  assetId,
  name,
  sortGeneration,
}: {
  assetId: string;
  name: string;
  sortGeneration: number;
}) {
  const reactId = useId();
  const instanceSuffix = reactId.replace(/:/g, "-");
  const playerId = `omakase-player-${assetId}-${instanceSuffix}`;

  const playerInitializedRef = useRef(false);
  const omakasePlayerRef = useRef<MockOmakasePlayer | null>(null);
  const isMountedRef = useRef(true);

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

    // Initialize if not already done
    if (!playerInitializedRef.current && playerDiv) {
      try {
        const player = new MockOmakasePlayer({ playerHTMLElementId: playerId });
        omakasePlayerRef.current = player;
        playerInitializedRef.current = true;
      } catch (_e) {
        /* init failed */
      }
    }

    // Cleanup — only on true unmount (mirrors AssetCard cleanup guard)
    return () => {
      if (omakasePlayerRef.current && !isMountedRef.current) {
        omakasePlayerRef.current.destroy();
        omakasePlayerRef.current = null;
        playerInitializedRef.current = false;
      }
    };
  }, [assetId, playerId, sortGeneration]);

  return (
    <div data-testid={`card-${assetId}`}>
      {/*
        The key changes when sortGeneration changes, forcing React to create
        a new DOM node. This simulates the container replacement that happens
        during real browser reconciliation when list items are reordered.
      */}
      <div
        key={`container-${sortGeneration}`}
        id={playerId}
        data-testid={`player-container-${assetId}`}
        style={{ width: "100%", height: "200px" }}
      />
      <span>{name}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SortableVideoList
// ---------------------------------------------------------------------------

interface Asset {
  InventoryID: string;
  name: string;
}

function SortableVideoList({
  assets,
  sortField,
  sortGeneration,
}: {
  assets: Asset[];
  sortField: "asc" | "desc";
  sortGeneration: number;
}) {
  const sorted = useMemo(() => {
    const copy = [...assets];
    copy.sort((a, b) => {
      const cmp = a.name.localeCompare(b.name);
      return sortField === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [assets, sortField]);

  return (
    <div data-testid="video-list">
      {sorted.map((asset) => (
        <VideoCard
          key={asset.InventoryID}
          assetId={asset.InventoryID}
          name={asset.name}
          sortGeneration={sortGeneration}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Property-based exploration test
// ---------------------------------------------------------------------------

describe("Bug Condition Exploration — Property 1: Player DOM Detaches After Sort Reorder", () => {
  beforeEach(() => {
    constructorCalls = [];
    destroyCalls = [];
  });

  /**
   * Property 1: Fault Condition — Player DOM Stays Connected After Sort
   *
   * For any set of 3+ video assets with initialized players, after a
   * sort-order change that causes container replacement (simulating real
   * browser DOM reconciliation), every player container SHOULD still
   * contain its player DOM subtree, the player should not be destroyed,
   * and no new OmakasePlayer constructor calls should occur.
   *
   * On UNFIXED code this MUST FAIL — proving the bug exists:
   * - Either the player DOM is detached (black screen), OR
   * - The stale detection fires and re-creates the player (unnecessary reload)
   *
   * **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
   */
  it("after sort reorder, every player container still contains its player DOM subtree", () => {
    const nameArb = fc
      .array(fc.constantFrom("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"), {
        minLength: 3,
        maxLength: 8,
      })
      .map((chars) => chars.join(""));

    const assetArb = fc
      .array(fc.record({ id: fc.uuid(), name: nameArb }), { minLength: 3, maxLength: 6 })
      .filter((arr) => {
        const ids = new Set(arr.map((a) => a.id));
        const names = new Set(arr.map((a) => a.name));
        if (ids.size !== arr.length || names.size !== arr.length) return false;
        // Ensure sorting actually changes the order
        const sorted = [...arr].sort((a, b) => a.name.localeCompare(b.name));
        return sorted.some((s, i) => s.id !== arr[i].id);
      });

    fc.assert(
      fc.property(assetArb, (assetData) => {
        constructorCalls = [];
        destroyCalls = [];

        const assets: Asset[] = assetData.map((a) => ({
          InventoryID: a.id,
          name: a.name,
        }));

        // Phase 1: Render with descending sort, generation 0
        const {
          rerender,
          unmount,
          container: rootEl,
        } = render(<SortableVideoList assets={assets} sortField="desc" sortGeneration={0} />);

        const initialCallCount = constructorCalls.length;
        expect(initialCallCount).toBe(assets.length);

        // Capture player DOM subtree references BEFORE sort
        // Use container.querySelector to avoid duplicate testid issues
        const playerSubtrees = new Map<string, Element>();
        for (const asset of assets) {
          const containerDiv = rootEl.querySelector(
            `[data-testid="player-container-${asset.InventoryID}"]`
          ) as HTMLElement;
          expect(containerDiv).not.toBeNull();
          const playerRoot = containerDiv!.querySelector(".omakase-player-root");
          expect(playerRoot).not.toBeNull();
          playerSubtrees.set(asset.InventoryID, playerRoot!);
        }

        // Phase 2: Trigger sort change — generation increments, causing container replacement
        act(() => {
          rerender(<SortableVideoList assets={assets} sortField="asc" sortGeneration={1} />);
        });

        // Phase 3: Assert the property
        for (const asset of assets) {
          const containerDiv = rootEl.querySelector(
            `[data-testid="player-container-${asset.InventoryID}"]`
          ) as HTMLElement;
          expect(containerDiv).not.toBeNull();

          const originalSubtree = playerSubtrees.get(asset.InventoryID)!;

          // The player DOM subtree must still be inside the CURRENT container
          expect(
            containerDiv!.contains(originalSubtree),
            `Player DOM for asset "${asset.name}" (${asset.InventoryID}) is detached from its container after sort`
          ).toBe(true);

          // The container must have children (not empty / black screen)
          expect(
            containerDiv!.children.length,
            `Container for asset "${asset.name}" has no children after sort (black screen condition)`
          ).toBeGreaterThan(0);
        }

        // No re-initialization should have occurred — player must be preserved
        // without being destroyed and recreated (which would cause video reload)
        expect(
          constructorCalls.length,
          `Player was re-initialized after sort (${constructorCalls.length} total calls vs ${initialCallCount} initial). Video was reloaded unnecessarily.`
        ).toBe(initialCallCount);

        unmount();
      }),
      { numRuns: 20, verbose: true }
    );
  });
});
