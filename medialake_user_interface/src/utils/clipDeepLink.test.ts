import { describe, expect, it } from "vitest";
import {
  buildClipDeepLinkSearch,
  clipStartSeconds,
  readClipDeepLink,
  CLIP_DEEP_LINK_PARAM,
} from "./clipDeepLink";

describe("clipStartSeconds", () => {
  it("reads a numeric start from clipData", () => {
    expect(clipStartSeconds({ clipData: { start: 123 } })).toBe(123);
  });

  it("reads start_seconds, which is what the search API returns", () => {
    expect(clipStartSeconds({ clipData: { start_seconds: 123, end_seconds: 129 } })).toBe(123);
  });

  it("parses start_timecode using the asset frame rate", () => {
    // 00:00:02:12 is 2.5s at 24fps but 2.48s at the 25fps default, so an exact
    // assertion here proves the rate came from the asset rather than the default.
    const asset = {
      clipData: { start_timecode: "00:00:02:12" },
      Metadata: { EmbeddedMetadata: { video: { FrameRate: 24 } } },
    };
    expect(clipStartSeconds(asset)).toBe(2.5);
  });

  it("falls back to the default frame rate when the asset does not state one", () => {
    expect(clipStartSeconds({ clipData: { start_timecode: "00:00:02:12" } })).toBe(2.48);
  });

  it("handles an ffprobe rational frame rate", () => {
    const asset = {
      clipData: { start_timecode: "00:00:01:00" },
      Metadata: { EmbeddedMetadata: { video: { r_frame_rate: "30000/1001" } } },
    };
    // One second of timecode is one second of media regardless of rate; the point
    // is that a rational rate parses instead of poisoning the result with NaN.
    expect(clipStartSeconds(asset)).toBeCloseTo(1, 5);
  });

  it("accepts a clips array of exactly one", () => {
    expect(clipStartSeconds({ clips: [{ start_seconds: 56 }] })).toBe(56);
  });

  it("returns undefined for a grouped result carrying many clips", () => {
    // Grouped ("Full") mode: the card stands for the whole asset, so there is no
    // single clicked moment to deep link to.
    const asset = { clips: [{ start_seconds: 1 }, { start_seconds: 2 }, { start_seconds: 3 }] };
    expect(clipStartSeconds(asset)).toBeUndefined();
  });

  it("returns undefined when there is no clip at all", () => {
    expect(clipStartSeconds({ InventoryID: "asset:uuid:x" })).toBeUndefined();
    expect(clipStartSeconds({ clips: [] })).toBeUndefined();
    expect(clipStartSeconds(null)).toBeUndefined();
    expect(clipStartSeconds(undefined)).toBeUndefined();
  });

  it("keeps a zero start, which is a real position", () => {
    expect(clipStartSeconds({ clipData: { start: 0 } })).toBe(0);
  });

  it("ignores a non-finite start rather than emitting NaN", () => {
    expect(clipStartSeconds({ clipData: { start: Number.NaN } })).toBeUndefined();
    expect(clipStartSeconds({ clipData: { start_timecode: "not-a-timecode" } })).toBeUndefined();
  });
});

describe("buildClipDeepLinkSearch", () => {
  it("emits both params", () => {
    const search = buildClipDeepLinkSearch({ searchTerm: "haircut", startTime: 123 });
    const params = new URLSearchParams(search);
    expect(params.get(CLIP_DEEP_LINK_PARAM.searchTerm)).toBe("haircut");
    expect(params.get(CLIP_DEEP_LINK_PARAM.startTime)).toBe("123");
  });

  it("returns an empty string when there is nothing to carry", () => {
    // So callers can append unconditionally without a dangling "?".
    expect(buildClipDeepLinkSearch({})).toBe("");
    expect(buildClipDeepLinkSearch({ searchTerm: "   " })).toBe("");
  });

  it("keeps a zero start time", () => {
    expect(buildClipDeepLinkSearch({ startTime: 0 })).toBe("?t=0");
  });

  it("drops a negative or non-finite start time", () => {
    expect(buildClipDeepLinkSearch({ startTime: -5 })).toBe("");
    expect(buildClipDeepLinkSearch({ startTime: Number.NaN })).toBe("");
    expect(buildClipDeepLinkSearch({ startTime: Number.POSITIVE_INFINITY })).toBe("");
  });

  it("rounds to milliseconds so the URL stays readable", () => {
    expect(buildClipDeepLinkSearch({ startTime: 12.3456789 })).toBe("?t=12.346");
  });

  it("encodes a term with spaces and symbols", () => {
    const search = buildClipDeepLinkSearch({ searchTerm: "barber shop & chair" });
    expect(readClipDeepLink(search).searchTerm).toBe("barber shop & chair");
  });
});

describe("readClipDeepLink", () => {
  it("round-trips what build produced", () => {
    const link = { searchTerm: "haircut", startTime: 123.5 };
    expect(readClipDeepLink(buildClipDeepLinkSearch(link))).toEqual(link);
  });

  it("returns an empty object for no params", () => {
    expect(readClipDeepLink("")).toEqual({});
    expect(readClipDeepLink("?")).toEqual({});
  });

  it("accepts the legacy searchTerm key", () => {
    expect(readClipDeepLink("?searchTerm=haircut").searchTerm).toBe("haircut");
  });

  it("prefers q over the legacy key", () => {
    expect(readClipDeepLink("?q=new&searchTerm=old").searchTerm).toBe("new");
  });

  it("reads a zero start time", () => {
    expect(readClipDeepLink("?t=0").startTime).toBe(0);
  });

  it("ignores a blank t instead of seeking to the head of the timeline", () => {
    // `Number("")` is 0, so a blank value would otherwise read as a real seek.
    expect(readClipDeepLink("?t=").startTime).toBeUndefined();
    expect(readClipDeepLink("?t=%20").startTime).toBeUndefined();
  });

  it("ignores an unparseable or negative t", () => {
    expect(readClipDeepLink("?t=abc").startTime).toBeUndefined();
    expect(readClipDeepLink("?t=-10").startTime).toBeUndefined();
  });

  it("ignores unrelated params", () => {
    expect(readClipDeepLink("?semantic=true&page=2")).toEqual({});
  });
});
