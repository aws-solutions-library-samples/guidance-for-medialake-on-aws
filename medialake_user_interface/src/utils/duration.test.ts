import { describe, it, expect } from "vitest";
import { formatDuration } from "./duration";

describe("formatDuration", () => {
  it("returns '0:00' for zero", () => {
    expect(formatDuration(0)).toBe("0:00");
  });

  it("returns '0:00' for NaN-ish input", () => {
    expect(formatDuration(NaN)).toBe("0:00");
  });

  it("formats seconds under a minute", () => {
    expect(formatDuration(9)).toBe("0:09");
    expect(formatDuration(59)).toBe("0:59");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(90)).toBe("1:30");
    expect(formatDuration(600)).toBe("10:00");
  });

  it("formats hours, minutes, and seconds", () => {
    expect(formatDuration(3661)).toBe("1:01:01");
    expect(formatDuration(7200)).toBe("2:00:00");
  });

  it("floors fractional seconds", () => {
    expect(formatDuration(61.9)).toBe("1:01");
  });
});
