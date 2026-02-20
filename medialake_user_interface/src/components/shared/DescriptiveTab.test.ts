import { describe, it, expect } from "vitest";
import { sortDescriptiveEntries, DescriptiveEntry } from "./DescriptiveTab";

function makeEntry(key: string, data: Partial<DescriptiveEntry["data"]> = {}): DescriptiveEntry {
  return {
    key,
    data: { result: "", prompt_label: "label", ...data },
  };
}

describe("sortDescriptiveEntries", () => {
  it("two runs, 3 chunks each — newest run first, chunks sorted by index", () => {
    const runA = "2026-02-18 10:33Z";
    const runB = "2026-02-17 09:00Z";
    const entries = [
      makeEntry("a3", { chunk_index: 3, pipeline_execution_id: "execA", run_timestamp: runA }),
      makeEntry("b2", { chunk_index: 2, pipeline_execution_id: "execB", run_timestamp: runB }),
      makeEntry("a1", { chunk_index: 1, pipeline_execution_id: "execA", run_timestamp: runA }),
      makeEntry("b3", { chunk_index: 3, pipeline_execution_id: "execB", run_timestamp: runB }),
      makeEntry("b1", { chunk_index: 1, pipeline_execution_id: "execB", run_timestamp: runB }),
      makeEntry("a2", { chunk_index: 2, pipeline_execution_id: "execA", run_timestamp: runA }),
    ];

    const result = sortDescriptiveEntries(entries);

    expect(result.map((e) => e.key)).toEqual(["a1", "a2", "a3", "b1", "b2", "b3"]);
  });

  it("mixed chunk + non-chunk — non-chunk entries preserved in original order after chunks", () => {
    const entries = [
      makeEntry("nc1", { prompt_label: "Summary" }),
      makeEntry("c1", {
        chunk_index: 1,
        pipeline_execution_id: "exec1",
        run_timestamp: "2026-02-18",
      }),
      makeEntry("nc2", { prompt_label: "Keywords" }),
      makeEntry("c2", {
        chunk_index: 2,
        pipeline_execution_id: "exec1",
        run_timestamp: "2026-02-18",
      }),
    ];

    const result = sortDescriptiveEntries(entries);

    expect(result.map((e) => e.key)).toEqual(["c1", "c2", "nc1", "nc2"]);
  });

  it("single run, 1 chunk — no crash, single entry returned", () => {
    const entries = [
      makeEntry("only", {
        chunk_index: 1,
        pipeline_execution_id: "exec1",
        run_timestamp: "2026-02-18",
      }),
    ];

    const result = sortDescriptiveEntries(entries);

    expect(result).toHaveLength(1);
    expect(result[0].key).toBe("only");
  });

  it("no chunk entries — returns entries in original order", () => {
    const entries = [
      makeEntry("a", { prompt_label: "A" }),
      makeEntry("b", { prompt_label: "B" }),
      makeEntry("c", { prompt_label: "C" }),
    ];

    const result = sortDescriptiveEntries(entries);

    expect(result).toEqual(entries);
  });

  it("failed chunk with chunk_index — appears in correct position within its run group", () => {
    const entries = [
      makeEntry("c2fail", {
        chunk_index: 2,
        chunk_status: "failed",
        pipeline_execution_id: "exec1",
        run_timestamp: "2026-02-18",
      }),
      makeEntry("c1ok", {
        chunk_index: 1,
        pipeline_execution_id: "exec1",
        run_timestamp: "2026-02-18",
      }),
    ];

    const result = sortDescriptiveEntries(entries);

    expect(result[0].key).toBe("c1ok");
    expect(result[1].key).toBe("c2fail");
  });
});
