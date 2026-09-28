import { describe, it, expect } from "vitest";
import { jobStatusKey, countUnseen } from "./NotificationCenter";

const notification = (jobId?: string, jobStatus?: string) =>
  ({ jobId, jobStatus }) as Parameters<typeof countUnseen>[0][number];

describe("unseen notification badge", () => {
  it("counts a job whose stored key matches a notification on screen", () => {
    const stored = new Set([jobStatusKey("job-1", "COMPLETED")]);
    expect(countUnseen([notification("job-1", "COMPLETED")], stored)).toBe(1);
  });

  it("uses the same key the writer produces", () => {
    // The regression this exists for: the writer was re-keyed to `jobId:status`
    // while the badge still matched on the notification's uuid, so the count
    // silently read zero even with unseen notifications present.
    const written = new Set<string>();
    written.add(jobStatusKey("job-1", "COMPLETED"));
    expect(countUnseen([notification("job-1", "COMPLETED")], written)).toBe(1);
  });

  it("ignores a stored key whose notification is no longer on screen", () => {
    const stored = new Set([jobStatusKey("job-gone", "COMPLETED")]);
    expect(countUnseen([notification("job-1", "COMPLETED")], stored)).toBe(0);
  });

  it("does not count a job that moved to a different status", () => {
    const stored = new Set([jobStatusKey("job-1", "PROCESSING")]);
    expect(countUnseen([notification("job-1", "COMPLETED")], stored)).toBe(0);
  });

  it("skips notifications that carry no job", () => {
    expect(countUnseen([notification(undefined, undefined)], new Set(["a:b"]))).toBe(0);
  });

  it("counts each unseen job once", () => {
    const stored = new Set([jobStatusKey("a", "COMPLETED"), jobStatusKey("b", "FAILED")]);
    expect(countUnseen([notification("a", "COMPLETED"), notification("b", "FAILED")], stored)).toBe(
      2
    );
  });
});
