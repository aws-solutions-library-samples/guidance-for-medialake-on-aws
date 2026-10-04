import { describe, it, expect } from "vitest";
import { expiresAtToMs } from "./NotificationCenter";

const ISO = "2026-10-05T10:00:00.000Z";
const MS = Date.parse(ISO);
const SECONDS = Math.floor(MS / 1000);

describe("expiresAtToMs", () => {
  it("reads the API's epoch seconds as seconds, not milliseconds", () => {
    // The regression this exists for: `new Date(1_791_190_800)` is January 1970,
    // so the notification was filtered out as expired the moment it was created.
    expect(expiresAtToMs(SECONDS)).toBe(SECONDS * 1000);
    expect(expiresAtToMs(SECONDS)).toBeGreaterThan(Date.parse("2026-01-01"));
  });

  it("accepts epoch seconds sent as a numeric string", () => {
    expect(expiresAtToMs(String(SECONDS))).toBe(SECONDS * 1000);
  });

  it("passes through a value already in milliseconds", () => {
    expect(expiresAtToMs(MS)).toBe(MS);
  });

  it("accepts the ISO form older rows were written with", () => {
    expect(expiresAtToMs(ISO)).toBe(MS);
  });

  it("returns null for a value it cannot read", () => {
    expect(expiresAtToMs("not-a-date")).toBeNull();
  });

  it("puts a seven-day expiry in the future, not in 1970", () => {
    const sevenDaysOut = Math.floor((Date.now() + 7 * 24 * 60 * 60 * 1000) / 1000);
    expect(expiresAtToMs(sevenDaysOut)!).toBeGreaterThan(Date.now());
  });
});
