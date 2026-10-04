import { describe, it, expect } from "vitest";
import { jobStatusKey, countUnseen, countActiveJobs } from "./NotificationCenter";

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

  it("counts a job once even while the sync holds duplicate notifications for it", () => {
    // Observed on staging: the sync briefly held two notifications for one job,
    // and because the key is job-level it matched both — badging one unseen
    // download as "2" until the dedupe pass landed.
    const stored = new Set([jobStatusKey("job-1", "COMPLETED")]);
    const duplicated = [notification("job-1", "COMPLETED"), notification("job-1", "COMPLETED")];
    expect(countUnseen(duplicated, stored)).toBe(1);
  });

  it("counts each unseen job once", () => {
    const stored = new Set([jobStatusKey("a", "COMPLETED"), jobStatusKey("b", "FAILED")]);
    expect(countUnseen([notification("a", "COMPLETED"), notification("b", "FAILED")], stored)).toBe(
      2
    );
  });
});

describe("active jobs badge", () => {
  it("counts an in-flight job once even with duplicate notifications", () => {
    // The window the first fix missed: before COMPLETED, `markAsUnseen` has not
    // fired, so the badge falls back to this counter — which double-counted the
    // duplicate and showed "2" for one download.
    const duplicated = [notification("job-1", "PROCESSING"), notification("job-1", "PROCESSING")];
    expect(countActiveJobs(duplicated)).toBe(1);
  });

  it("counts two distinct in-flight jobs as two", () => {
    expect(countActiveJobs([notification("a", "STAGING"), notification("b", "INITIATED")])).toBe(2);
  });

  it("excludes terminal statuses", () => {
    expect(countActiveJobs([notification("a", "COMPLETED"), notification("b", "FAILED")])).toBe(0);
  });

  it("ignores notifications with no job", () => {
    expect(countActiveJobs([notification(undefined, undefined)])).toBe(0);
  });
});
