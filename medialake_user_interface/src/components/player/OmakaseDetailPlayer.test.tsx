/**
 * Regression test for the marker panel showing 0 markers.
 *
 * The marker tracks and their marker bars were correct, but the sidebar panel —
 * which lives in the *parent* — sat permanently at "0 markers". The cause was
 * this component publishing its result to `onPlayerReady` exactly once, keyed on
 * `result.isReady`, so the parent captured the initial empty marker arrays and
 * never saw another value.
 *
 * These tests pin the contract the parent depends on: republish whenever the
 * result changes, and don't republish when nothing has.
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import React from "react";

// `@byomakase/omakase-player` cannot be imported under jsdom (media-chrome and
// media-captions touch browser APIs at module-import time), and this test is
// about the publish contract rather than the player. Both the hook that owns the
// player and the theme helper that imports the package are mocked out.
const useDetailPlayerMock = vi.fn();

vi.mock("./useDetailPlayer", () => ({
  useDetailPlayer: (...args: unknown[]) => useDetailPlayerMock(...args),
}));

vi.mock("./createOmakaseThemeConfig", () => ({
  createOmakaseThemeConfig: () => ({ cssVars: {}, chromingTheme: "DEFAULT" }),
}));

vi.mock("./usePlayerKeyboardShortcutsCore", () => ({
  usePlayerKeyboardShortcutsCore: () => undefined,
}));

import { OmakaseDetailPlayer } from "./OmakaseDetailPlayer";

/** A stand-in for the memoized object `useDetailPlayer` returns. */
function makeResult(overrides: Record<string, unknown> = {}) {
  return {
    isReady: true,
    userMarkers: [],
    semanticMarkers: [],
    playerRef: { current: null },
    userTrackRef: { current: null },
    semanticTrackRef: { current: null },
    duration: 0,
    isPlaying: false,
    volume: 100,
    muted: false,
    seek: vi.fn(),
    play: vi.fn(),
    pause: vi.fn(),
    setVolume: vi.fn(),
    mute: vi.fn(),
    unmute: vi.fn(),
    setPlaybackRate: vi.fn(),
    toggleFullscreen: vi.fn(),
    addUserMarker: vi.fn(),
    updateMarker: vi.fn(),
    removeUserMarker: vi.fn(),
    setSemanticMarkers: vi.fn(),
    ...overrides,
  };
}

const props = {
  src: "https://example.test/proxy.mp4",
  mediaType: "video" as const,
  assetId: "asset:uuid:test",
};

beforeEach(() => {
  useDetailPlayerMock.mockReset();
});

describe("OmakaseDetailPlayer marker publishing", () => {
  it("does not publish until the player is ready", () => {
    const onPlayerReady = vi.fn();
    useDetailPlayerMock.mockReturnValue(makeResult({ isReady: false }));

    render(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);

    expect(onPlayerReady).not.toHaveBeenCalled();
  });

  it("republishes when markers change so the parent's panel can update", () => {
    const onPlayerReady = vi.fn();

    const first = makeResult({ userMarkers: [] });
    useDetailPlayerMock.mockReturnValue(first);
    const { rerender } = render(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);

    expect(onPlayerReady).toHaveBeenCalledTimes(1);
    expect(onPlayerReady.mock.calls[0][0].userMarkers).toHaveLength(0);

    // A marker lands on the track: `useDetailPlayer`'s memo produces a new object.
    const second = makeResult({
      userMarkers: [{ id: "m1", kind: "user", startTime: 1, endTime: 2 }],
    });
    useDetailPlayerMock.mockReturnValue(second);
    rerender(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);

    expect(onPlayerReady).toHaveBeenCalledTimes(2);
    expect(onPlayerReady.mock.calls[1][0].userMarkers).toHaveLength(1);
  });

  it("republishes when semantic markers arrive", () => {
    const onPlayerReady = vi.fn();

    useDetailPlayerMock.mockReturnValue(makeResult());
    const { rerender } = render(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);
    expect(onPlayerReady).toHaveBeenCalledTimes(1);

    useDetailPlayerMock.mockReturnValue(
      makeResult({
        semanticMarkers: [
          { id: "s1", kind: "semantic", startTime: 123, endTime: 129, score: 0.55 },
        ],
      })
    );
    rerender(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);

    expect(onPlayerReady).toHaveBeenCalledTimes(2);
    expect(onPlayerReady.mock.calls[1][0].semanticMarkers).toHaveLength(1);
  });

  it("does not republish when the result is unchanged", () => {
    const onPlayerReady = vi.fn();

    // A stable object is what the real memo returns across unrelated re-renders.
    const stable = makeResult();
    useDetailPlayerMock.mockReturnValue(stable);

    const { rerender } = render(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);
    rerender(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);
    rerender(<OmakaseDetailPlayer {...props} onPlayerReady={onPlayerReady} />);

    expect(onPlayerReady).toHaveBeenCalledTimes(1);
  });
});
