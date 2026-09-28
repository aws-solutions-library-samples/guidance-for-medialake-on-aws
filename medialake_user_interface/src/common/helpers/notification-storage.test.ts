import { describe, it, expect, beforeEach, vi } from "vitest";
import { pruneOversizedNotificationStorage } from "./notification-storage";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("pruneOversizedNotificationStorage", () => {
  it("drops a key that has grown past its useful size", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    // The shape seen in production: tens of thousands of per-session uuids.
    const bloated = JSON.stringify(
      Array.from(
        { length: 20_000 },
        (_, i) => `f47ac10b-58cc-4372-a567-${String(i).padStart(12, "0")}`
      )
    );
    expect(bloated.length).toBeGreaterThan(256 * 1024);
    localStorage.setItem("medialake_unseen_notifications", bloated);

    pruneOversizedNotificationStorage();

    expect(localStorage.getItem("medialake_unseen_notifications")).toBeNull();
  });

  it("leaves a normally sized key in place", () => {
    localStorage.setItem("medialake_unseen_notifications", '["job-1:COMPLETED"]');
    pruneOversizedNotificationStorage();
    expect(localStorage.getItem("medialake_unseen_notifications")).toBe('["job-1:COMPLETED"]');
  });

  it("does not touch keys outside the notification bookkeeping", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    localStorage.setItem("medialake-auth-token", "jwt");
    localStorage.setItem("medialake_unseen_notifications", JSON.stringify(["x".repeat(300_000)]));

    pruneOversizedNotificationStorage();

    expect(localStorage.getItem("medialake-auth-token")).toBe("jwt");
  });
});
