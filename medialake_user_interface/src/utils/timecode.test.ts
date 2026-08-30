import { describe, expect, it } from "vitest";

import {
  DEFAULT_FPS,
  RANGE_SEPARATOR,
  formatDuration,
  formatSmpte,
  formatTimeRange,
  formatTimecode,
  formatTimecodeRange,
  getAssetFrameRate,
  isValidTime,
  parseFrameRate,
  parseTimecode,
  secondsToApiTimecode,
} from "./timecode";

describe("formatTimecode", () => {
  it("omits the hours group below an hour", () => {
    expect(formatTimecode(65)).toBe("01:05");
    expect(formatTimecode(0)).toBe("00:00");
  });

  it("carries hours instead of overflowing the minutes field", () => {
    // The bug this replaces: BatchOperations.formatClock rendered this as "65:00".
    expect(formatTimecode(3900)).toBe("01:05:00");
    expect(formatTimecode(3599)).toBe("59:59");
    expect(formatTimecode(3600)).toBe("01:00:00");
  });

  it("can be forced to show hours for column alignment", () => {
    expect(formatTimecode(65, { alwaysShowHours: true })).toBe("00:01:05");
  });

  it("truncates rather than rounds, so a time never reads ahead of itself", () => {
    expect(formatTimecode(59.99)).toBe("00:59");
  });

  it("returns null for unusable input", () => {
    expect(formatTimecode(undefined)).toBeNull();
    expect(formatTimecode(null)).toBeNull();
    expect(formatTimecode(Number.NaN)).toBeNull();
    expect(formatTimecode(Number.POSITIVE_INFINITY)).toBeNull();
    expect(formatTimecode(-1)).toBeNull();
  });

  describe("with frames", () => {
    it("always fully qualifies a SMPTE timecode", () => {
      // Even below an hour: "01:05:12" would be ambiguous.
      expect(formatTimecode(65.5, { showFrames: true, fps: 50 })).toBe("00:01:05:25");
    });

    it("derives the frame number from the supplied frame rate", () => {
      expect(formatSmpte(1.5, 25)).toBe("00:00:01:12");
      expect(formatSmpte(1.5, 50)).toBe("00:00:01:25");
    });

    it("falls back to DEFAULT_FPS when the rate is unknown or unusable", () => {
      expect(formatSmpte(1.5)).toBe(formatSmpte(1.5, DEFAULT_FPS));
      expect(formatSmpte(1.5, 0)).toBe(formatSmpte(1.5, DEFAULT_FPS));
      expect(formatSmpte(1.5, Number.NaN)).toBe(formatSmpte(1.5, DEFAULT_FPS));
    });

    it("never emits a frame index equal to the frame rate", () => {
      // Floating point drift on a near-whole second would otherwise yield ":25"
      // at 25fps, which is not a valid frame index.
      expect(formatSmpte(9.9999, 25)).toBe("00:00:09:24");
      expect(formatSmpte(9.9999, 29.97)).toBe("00:00:09:29");
    });

    it("emits frame 00 for whole seconds", () => {
      expect(formatSmpte(10, 25)).toBe("00:00:10:00");
    });
  });
});

describe("RANGE_SEPARATOR", () => {
  it("uses narrow no-break spaces so the range reads tight and cannot break before the dash", () => {
    expect(RANGE_SEPARATOR).toBe("\u202f\u2013\u202f");
    expect(RANGE_SEPARATOR).not.toMatch(/[ \u2009]/);
  });
});

describe("formatTimeRange", () => {
  it("joins both ends with an en dash", () => {
    expect(formatTimeRange(65, 130)).toBe(`01:05${RANGE_SEPARATOR}02:10`);
  });

  it("collapses a zero-length range to a single timecode", () => {
    expect(formatTimeRange(65, 65)).toBe("01:05");
  });

  it("returns null when either end is unusable", () => {
    // A half-open range reads as though the data were truncated.
    expect(formatTimeRange(65, undefined)).toBeNull();
    expect(formatTimeRange(undefined, 130)).toBeNull();
    expect(formatTimeRange(Number.NaN, 130)).toBeNull();
  });

  it("passes formatting options through to both ends", () => {
    expect(formatTimeRange(1, 2, { showFrames: true, fps: 25 })).toBe(
      `00:00:01:00${RANGE_SEPARATOR}00:00:02:00`
    );
  });
});

describe("formatTimecodeRange", () => {
  it("joins two source timecode strings", () => {
    expect(formatTimecodeRange("00:00:10:00", "00:00:25:00")).toBe(
      `00:00:10:00${RANGE_SEPARATOR}00:00:25:00`
    );
  });

  it("treats blank and whitespace-only ends as absent", () => {
    expect(formatTimecodeRange("00:00:10:00", "")).toBeNull();
    expect(formatTimecodeRange("   ", "00:00:25:00")).toBeNull();
    expect(formatTimecodeRange(undefined, undefined)).toBeNull();
  });

  it("collapses an identical pair", () => {
    expect(formatTimecodeRange("00:00:10:00", "00:00:10:00")).toBe("00:00:10:00");
  });
});

describe("formatDuration", () => {
  it("reads as a duration, not a clock", () => {
    expect(formatDuration(6)).toBe("6s");
    expect(formatDuration(65)).toBe("1m 05s");
    expect(formatDuration(3900)).toBe("1h 05m");
  });

  it("returns null for unusable input", () => {
    expect(formatDuration(undefined)).toBeNull();
    expect(formatDuration(-1)).toBeNull();
  });
});

describe("parseTimecode", () => {
  it("round-trips a SMPTE timecode at the same frame rate", () => {
    expect(parseTimecode("00:00:01:12", 25)).toBeCloseTo(1.48, 5);
    expect(parseTimecode(formatSmpte(1.48, 25), 25)).toBeCloseTo(1.48, 5);
  });

  it("accepts the drop-frame separator", () => {
    expect(parseTimecode("00:00:01;12", 25)).toBeCloseTo(1.48, 5);
  });

  it("rejects a frame index at or beyond the frame rate", () => {
    // Rolling it into the next second would silently move the marker.
    expect(parseTimecode("00:00:01:25", 25)).toBeNull();
    expect(parseTimecode("00:00:01:99", 25)).toBeNull();
  });

  it("accepts clock forms without frames", () => {
    expect(parseTimecode("01:05:00")).toBe(3900);
    expect(parseTimecode("01:05")).toBe(65);
    expect(parseTimecode("90:00")).toBe(5400);
  });

  it("accepts fractional seconds", () => {
    expect(parseTimecode("00:00:01.500")).toBeCloseTo(1.5, 5);
    expect(parseTimecode("01:05.250")).toBeCloseTo(65.25, 5);
    expect(parseTimecode("12.5")).toBeCloseTo(12.5, 5);
  });

  it("accepts bare seconds", () => {
    expect(parseTimecode("42")).toBe(42);
  });

  it("tolerates surrounding whitespace", () => {
    expect(parseTimecode("  00:01:05  ")).toBe(65);
  });

  it("returns null for junk rather than defaulting to zero", () => {
    expect(parseTimecode("")).toBeNull();
    expect(parseTimecode("   ")).toBeNull();
    expect(parseTimecode("abc")).toBeNull();
    expect(parseTimecode("1:2:3:4:5")).toBeNull();
    expect(parseTimecode(undefined)).toBeNull();
    expect(parseTimecode(null)).toBeNull();
  });
});

describe("parseFrameRate", () => {
  it("accepts numbers", () => {
    expect(parseFrameRate(25)).toBe(25);
    expect(parseFrameRate(29.97)).toBe(29.97);
  });

  it("accepts decimal strings", () => {
    expect(parseFrameRate("29.97")).toBeCloseTo(29.97, 5);
  });

  it("accepts ffprobe rationals", () => {
    expect(parseFrameRate("24/1")).toBe(24);
    expect(parseFrameRate("30000/1001")).toBeCloseTo(29.97, 2);
  });

  it("rejects non-positive, non-finite and malformed values", () => {
    expect(parseFrameRate(0)).toBeUndefined();
    expect(parseFrameRate(-25)).toBeUndefined();
    expect(parseFrameRate(Number.NaN)).toBeUndefined();
    expect(parseFrameRate("24/0")).toBeUndefined();
    expect(parseFrameRate("")).toBeUndefined();
    expect(parseFrameRate("abc")).toBeUndefined();
    expect(parseFrameRate(undefined)).toBeUndefined();
  });
});

describe("getAssetFrameRate", () => {
  const withVideoMetadata = (video: unknown) => ({
    Metadata: { EmbeddedMetadata: { video } },
  });

  it("reads the first entry of the video metadata array", () => {
    expect(getAssetFrameRate(withVideoMetadata([{ FrameRate: "50" }]))).toBe(50);
  });

  it("reads a non-array video metadata object", () => {
    expect(getAssetFrameRate(withVideoMetadata({ FrameRate: 24 }))).toBe(24);
  });

  it("reads the ffprobe rational form", () => {
    expect(getAssetFrameRate(withVideoMetadata([{ r_frame_rate: "30000/1001" }]))).toBeCloseTo(
      29.97,
      2
    );
  });

  it("falls back to general metadata", () => {
    expect(
      getAssetFrameRate({
        Metadata: { EmbeddedMetadata: { general: { FrameRate: "23.976" } } },
      })
    ).toBeCloseTo(23.976, 3);
  });

  it("returns a genuine 25 rather than treating it as a miss", () => {
    // The old sidebar implementation used `if (fps === 25)` as its
    // "not found yet" sentinel, so a real 25fps asset fell through.
    expect(getAssetFrameRate(withVideoMetadata([{ FrameRate: 25 }]))).toBe(25);
  });

  it("returns undefined when the rate is unknown, so callers can tell", () => {
    expect(getAssetFrameRate(undefined)).toBeUndefined();
    expect(getAssetFrameRate({})).toBeUndefined();
    expect(getAssetFrameRate(withVideoMetadata([]))).toBeUndefined();
    expect(getAssetFrameRate(withVideoMetadata([{ FrameRate: "n/a" }]))).toBeUndefined();
  });
});

describe("secondsToApiTimecode", () => {
  it("always produces a wire-format timecode", () => {
    expect(secondsToApiTimecode(10, 25)).toBe("00:00:10:00");
  });

  it("clamps unusable input rather than returning null", () => {
    // The API contract has no representation for "unknown".
    expect(secondsToApiTimecode(Number.NaN)).toBe("00:00:00:00");
    expect(secondsToApiTimecode(-5)).toBe("00:00:00:00");
  });
});

describe("isValidTime", () => {
  it("accepts finite non-negative numbers", () => {
    expect(isValidTime(0)).toBe(true);
    expect(isValidTime(1.5)).toBe(true);
  });

  it("rejects everything else", () => {
    expect(isValidTime(-1)).toBe(false);
    expect(isValidTime(Number.NaN)).toBe(false);
    expect(isValidTime(Number.POSITIVE_INFINITY)).toBe(false);
    expect(isValidTime("10")).toBe(false);
    expect(isValidTime(null)).toBe(false);
    expect(isValidTime(undefined)).toBe(false);
  });
});
