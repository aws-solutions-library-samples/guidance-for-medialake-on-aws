import { describe, it, expect } from "vitest";
import { formatDate, formatDateOnly } from "./dateFormat";

describe("formatDate", () => {
  it("returns empty string for null/undefined", () => {
    expect(formatDate(null)).toBe("");
    expect(formatDate(undefined)).toBe("");
  });

  it("formats a valid ISO string", () => {
    const result = formatDate("2025-06-18T15:45:00Z");
    expect(result).toContain("2025");
    expect(result).toContain("Jun");
  });
});

describe("formatDateOnly", () => {
  it("returns empty string for null/undefined", () => {
    expect(formatDateOnly(null)).toBe("");
    expect(formatDateOnly(undefined)).toBe("");
  });

  it("returns empty string for invalid date", () => {
    expect(formatDateOnly("garbage")).toBe("");
  });

  it("formats ISO string to date-only", () => {
    const result = formatDateOnly("2025-06-18T15:45:00Z");
    expect(result).toContain("Jun");
    expect(result).toContain("18");
    expect(result).toContain("2025");
    // Should NOT contain time info
    expect(result).not.toMatch(/\d{1,2}:\d{2}/);
  });

  it("handles epoch seconds (10-digit)", () => {
    const result = formatDateOnly(1718729100);
    expect(result).toContain("2024");
  });

  it("handles epoch milliseconds (13-digit)", () => {
    const result = formatDateOnly(1718729100000);
    expect(result).toContain("2024");
  });

  it("handles string epoch", () => {
    const result = formatDateOnly("1718729100");
    expect(result).toContain("2024");
  });
});
