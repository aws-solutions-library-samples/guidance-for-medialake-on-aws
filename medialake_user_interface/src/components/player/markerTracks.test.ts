import { describe, expect, it, vi } from "vitest";

/**
 * The real package is not imported here.
 *
 * `@byomakase/omakase-player` pulls in media-chrome and media-captions, which
 * touch browser APIs jsdom does not implement (`matchMedia`, and a base class
 * media-captions extends) at *module-import* time — so merely importing the
 * package for an enum throws before any assertion runs. Stubbing each gap in turn
 * is a losing game, and these tests are about our own conversion and projection
 * logic, not Omakase's. So the boundary is mocked with the two things we use.
 */
vi.mock("@byomakase/omakase-player", () => {
  let counter = 0;
  return {
    TimedItemTemporalType: {
      MOMENT: "MOMENT",
      SPAN: "SPAN",
      SPAN_START: "SPAN_START",
      SPAN_END: "SPAN_END",
    },
    TimedItemsTrackEventType: {
      TIMED_ITEMS_TRACK_ITEMS_ADDED: "TIMED_ITEMS_TRACK_ITEMS_ADDED",
      TIMED_ITEMS_TRACK_ITEMS_DELETED: "TIMED_ITEMS_TRACK_ITEMS_DELETED",
      TIMED_ITEMS_TRACK_ITEMS_UPDATED: "TIMED_ITEMS_TRACK_ITEMS_UPDATED",
    },
    MarkerTrack: class {},
    // Mirrors DefaultMarker's observable surface: an id, and a `state` snapshot
    // carrying the temporal, label and data payload.
    DefaultMarker: class {
      id: string;
      state: Record<string, unknown>;
      constructor(args: { temporal: unknown; label?: string; data?: Record<string, unknown> }) {
        counter += 1;
        this.id = `marker-${counter}`;
        this.state = {
          id: this.id,
          temporal: args.temporal,
          label: args.label,
          data: args.data ?? {},
        };
      }
    },
  };
});

import { TimedItemTemporalType } from "@byomakase/omakase-player";
import { createMarker, readSpan, toDetailMarker, toSpanTemporal } from "./markerTracks";

/** Minimal MarkerState stand-in; only the fields the projection reads. */
const markerState = (overrides: Record<string, unknown> = {}) =>
  ({
    id: "marker-1",
    temporal: toSpanTemporal(10, 20),
    data: {},
    label: undefined,
    ...overrides,
  }) as never;

describe("toSpanTemporal", () => {
  it("emits seconds as strings, which is what Omakase expects", () => {
    // TimedItemTemporal carries times as strings, not numbers — the single
    // easiest thing to get wrong when moving between our model and the player.
    expect(toSpanTemporal(56, 63)).toEqual({
      type: TimedItemTemporalType.SPAN,
      start: "56",
      end: "63",
    });
  });

  it("preserves sub-second precision", () => {
    expect(toSpanTemporal(1.5, 2.25)).toEqual({
      type: TimedItemTemporalType.SPAN,
      start: "1.5",
      end: "2.25",
    });
  });
});

describe("readSpan", () => {
  it("round-trips a span back to numbers", () => {
    expect(readSpan(toSpanTemporal(56, 63))).toEqual({ start: 56, end: 63 });
  });

  it("rejects temporal shapes a span marker should never have", () => {
    // A MOMENT has `time`, not `start`/`end`; treating it as a span would read
    // undefined and produce NaN.
    expect(readSpan({ type: TimedItemTemporalType.MOMENT, time: "42" })).toBeNull();
    expect(readSpan({ type: TimedItemTemporalType.SPAN_START, start: "42" })).toBeNull();
    expect(readSpan({ type: TimedItemTemporalType.SPAN_END, end: "42" })).toBeNull();
  });

  it("rejects unparseable values rather than yielding NaN", () => {
    expect(readSpan({ type: TimedItemTemporalType.SPAN, start: "abc", end: "63" })).toBeNull();
    expect(readSpan({ type: TimedItemTemporalType.SPAN, start: "", end: "" })).toBeNull();
  });
});

describe("toDetailMarker", () => {
  it("projects times, label and the attached payload", () => {
    const projected = toDetailMarker(
      markerState({
        id: "abc",
        temporal: toSpanTemporal(5, 9),
        label: "Scene cut",
        data: { kind: "semantic", color: "#17C964", score: 0.62, modelVersion: "3.0" },
      })
    );

    expect(projected).toEqual({
      id: "abc",
      kind: "semantic",
      startTime: 5,
      endTime: 9,
      label: "Scene cut",
      color: "#17C964",
      score: 0.62,
      modelVersion: "3.0",
    });
  });

  it("defaults to a user marker when the payload says nothing", () => {
    // Markers created outside our helpers (or by a future Omakase surface) must
    // not be silently classed as semantic, which is the read-only kind.
    expect(toDetailMarker(markerState({ data: {} }))?.kind).toBe("user");
    expect(toDetailMarker(markerState({ data: undefined }))?.kind).toBe("user");
  });

  it("returns null for a marker with no usable span", () => {
    expect(
      toDetailMarker(markerState({ temporal: { type: TimedItemTemporalType.MOMENT, time: "3" } }))
    ).toBeNull();
  });
});

describe("createMarker", () => {
  it("carries kind and display fields in the marker's data payload", () => {
    // `data` is what makes a marker self-describing on the way back out of
    // Omakase, replacing the coordinator's side table keyed by id.
    const marker = createMarker({
      kind: "user",
      startTime: 1,
      endTime: 4,
      label: "Marker 1",
      color: "#abcdef",
    });

    const projected = toDetailMarker(marker.state as never);
    expect(projected).toMatchObject({
      kind: "user",
      startTime: 1,
      endTime: 4,
      label: "Marker 1",
      color: "#abcdef",
    });
  });

  it("gives every marker a distinct id", () => {
    const a = createMarker({ kind: "user", startTime: 0, endTime: 1 });
    const b = createMarker({ kind: "user", startTime: 0, endTime: 1 });
    expect(a.id).not.toBe(b.id);
  });

  it("round-trips a semantic marker's score and model version", () => {
    const marker = createMarker({
      kind: "semantic",
      startTime: 56,
      endTime: 63,
      score: 0.5705,
      modelVersion: "3.0",
    });

    const projected = toDetailMarker(marker.state as never);
    expect(projected?.score).toBeCloseTo(0.5705, 4);
    expect(projected?.modelVersion).toBe("3.0");
  });
});
