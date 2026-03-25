import { describe, it, expect } from "vitest";
import { formatLocalDateTime, formatRelativeTime, isValidISOString } from "./dateUtils";

describe("formatLocalDateTime", () => {
  it("returns empty string for null/undefined", () => {
    expect(formatLocalDateTime(null)).toBe("");
    expect(formatLocalDateTime(undefined)).toBe("");
  });

  it("returns status labels verbatim", () => {
    expect(formatLocalDateTime("In Progress")).toBe("In Progress");
    expect(formatLocalDateTime("Running")).toBe("Running");
  });

  it("returns 'Invalid date' for garbage input", () => {
    expect(formatLocalDateTime("not-a-date-123")).toBe("Invalid date");
  });

  it("formats a valid ISO string", () => {
    const result = formatLocalDateTime("2025-06-18T15:45:00Z");
    // Should contain date parts — exact format depends on locale/timezone
    expect(result).toContain("2025");
    expect(result).toContain("Jun");
  });

  it("formats epoch seconds (10-digit)", () => {
    // 1718729100 = 2024-06-18T15:45:00Z
    const result = formatLocalDateTime(1718729100);
    expect(result).toContain("2024");
  });

  it("formats epoch milliseconds (13-digit)", () => {
    const result = formatLocalDateTime(1718729100000);
    expect(result).toContain("2024");
  });

  it("includes seconds when showSeconds is true", () => {
    const withSeconds = formatLocalDateTime("2025-06-18T15:45:30Z", { showSeconds: true });
    // Should contain the seconds portion
    expect(withSeconds).toMatch(/30/);
  });
});

describe("formatRelativeTime", () => {
  it("returns empty string for null/undefined", () => {
    expect(formatRelativeTime(null)).toBe("");
    expect(formatRelativeTime(undefined)).toBe("");
  });

  it("returns status labels verbatim", () => {
    expect(formatRelativeTime("Running")).toBe("Running");
  });

  it("returns 'Invalid date' for garbage", () => {
    expect(formatRelativeTime("not-a-date-123")).toBe("Invalid date");
  });

  it("returns a relative string for a recent date", () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const result = formatRelativeTime(fiveMinutesAgo);
    expect(result).toContain("minutes ago");
  });
});

describe("isValidISOString", () => {
  it("returns false for null/undefined", () => {
    expect(isValidISOString(null)).toBe(false);
    expect(isValidISOString(undefined)).toBe(false);
  });

  it("returns false for status labels", () => {
    expect(isValidISOString("Running")).toBe(false);
  });

  it("returns true for valid ISO strings", () => {
    expect(isValidISOString("2025-06-18T15:45:00Z")).toBe(true);
  });

  it("returns true for epoch numbers", () => {
    expect(isValidISOString(1718729100)).toBe(true);
  });
});
