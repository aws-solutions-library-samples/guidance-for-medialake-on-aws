import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { isTokenExpiringSoon } from "./token-helper";

// Create a minimal JWT token with a given exp claim
function createToken(exp: number): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ exp }));
  return `${header}.${payload}.fake-signature`;
}

describe("isTokenExpiringSoon", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Fix time to a known epoch: 2025-01-01T00:00:00Z = 1735689600
    vi.setSystemTime(new Date("2025-01-01T00:00:00Z"));
  });

  it("returns false when token has plenty of time left", () => {
    const currentEpoch = 1735689600;
    // Expires in 600 seconds (10 min), buffer is 300 (5 min)
    const token = createToken(currentEpoch + 600);
    expect(isTokenExpiringSoon(token, 300)).toBe(false);
  });

  it("returns true when token expires within buffer", () => {
    const currentEpoch = 1735689600;
    // Expires in 200 seconds, buffer is 300
    const token = createToken(currentEpoch + 200);
    expect(isTokenExpiringSoon(token, 300)).toBe(true);
  });

  it("returns true when token is already expired", () => {
    const currentEpoch = 1735689600;
    const token = createToken(currentEpoch - 100);
    expect(isTokenExpiringSoon(token)).toBe(true);
  });

  it("returns false at exactly the buffer boundary (strict less-than)", () => {
    const currentEpoch = 1735689600;
    // Expires in exactly 300 seconds, buffer is 300 — 300 < 300 is false
    const token = createToken(currentEpoch + 300);
    expect(isTokenExpiringSoon(token, 300)).toBe(false);
  });

  it("returns true for invalid/malformed tokens", () => {
    expect(isTokenExpiringSoon("not-a-jwt")).toBe(true);
    expect(isTokenExpiringSoon("")).toBe(true);
  });

  it("uses default buffer of 300 seconds", () => {
    const currentEpoch = 1735689600;
    // Expires in 400 seconds — more than default 300 buffer
    const token = createToken(currentEpoch + 400);
    expect(isTokenExpiringSoon(token)).toBe(false);
  });

  afterEach(() => {
    vi.useRealTimers();
  });
});
