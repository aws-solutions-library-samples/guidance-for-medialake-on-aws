import { describe, it, expect, vi, beforeEach } from "vitest";
import { MarkerSyncCoordinator } from "./MarkerSyncCoordinator";
import type {
  Clock,
  IdGenerator,
  StoragePort,
  SyncCoordinatorEvent,
  MarkerSyncEnvelope,
} from "./ports";

function makeClock(start = 1000): Clock {
  let t = start;
  return { now: () => t++ };
}

function makeIdGen(ids: string[]): IdGenerator {
  let i = 0;
  return { next: () => ids[i++] };
}

function makeStorage(
  initial: MarkerSyncEnvelope[] = []
): StoragePort & { save: ReturnType<typeof vi.fn>; load: ReturnType<typeof vi.fn> } {
  let data = [...initial];
  return {
    load: vi.fn(() => data),
    save: vi.fn((_assetId: string, envelopes: MarkerSyncEnvelope[]) => {
      data = envelopes;
    }),
  };
}

function makeCoordinator(
  overrides: {
    clock?: Clock;
    idGenerator?: IdGenerator;
    storage?: ReturnType<typeof makeStorage>;
    assetId?: string;
    ids?: string[];
  } = {}
) {
  const ids = overrides.ids ?? [
    "session-1",
    "id-1",
    "id-2",
    "id-3",
    "id-4",
    "id-5",
    "id-6",
    "id-7",
    "id-8",
    "id-9",
    "id-10",
  ];
  const storage = overrides.storage ?? makeStorage();
  const coordinator = new MarkerSyncCoordinator({
    clock: overrides.clock ?? makeClock(),
    idGenerator: overrides.idGenerator ?? makeIdGen(ids),
    storage,
    assetId: overrides.assetId ?? "asset-1",
  });
  return { coordinator, storage };
}

function collectEvents(coordinator: MarkerSyncCoordinator) {
  const events: SyncCoordinatorEvent[] = [];
  const payloads: Record<string, unknown[]> = {};
  const allEvents: SyncCoordinatorEvent[] = [
    "MARKER_COMMIT_REQUESTED",
    "MARKER_COMMIT_CONFIRMED",
    "MARKER_COMMIT_FAILED_ROLLBACK_APPLIED",
    "MARKER_PREVIEW_UPDATED",
    "MARKER_SYSTEM_NOT_READY",
    "STALE_ACK_IGNORED",
    "SESSION_MISMATCH_IGNORED",
  ];
  for (const e of allEvents) {
    payloads[e] = [];
    coordinator.on(e, (payload) => {
      events.push(e);
      payloads[e].push(payload);
    });
  }
  return { events, payloads };
}

describe("MarkerSyncCoordinator", () => {
  describe("Scenario 1 — Stale ack ignored", () => {
    it("emits STALE_ACK_IGNORED when ack revision < current revision", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1", "op-1", "op-2"] });
      coordinator.setReady(true);
      const { events, payloads } = collectEvents(coordinator);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track"); // mk-1, rev=1
      coordinator.update("mk-1", { label: "a" }, "track"); // op-1, rev=2
      coordinator.update("mk-1", { label: "b" }, "track"); // op-2, rev=3

      coordinator.acknowledgeCommit("op-1"); // op-1 revision=2 < current=3

      expect(events).toContain("STALE_ACK_IGNORED");
      const stalePayload = payloads["STALE_ACK_IGNORED"][0] as any;
      expect(stalePayload.currentRevision).toBe(3);
    });
  });

  describe("Scenario 1b — Successful ack persists and clears pendingOpId", () => {
    it("persists envelope with cleared pendingOpId after acknowledgeCommit", () => {
      const { coordinator, storage } = makeCoordinator({ ids: ["session-1", "mk-1", "op-1"] });
      coordinator.setReady(true);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track");
      coordinator.update("mk-1", { label: "a" }, "track"); // op-1, rev=2

      const saveCountBeforeAck = storage.save.mock.calls.length;
      coordinator.acknowledgeCommit("op-1");

      expect(storage.save).toHaveBeenCalledTimes(saveCountBeforeAck + 1);
      const lastSaveCall = storage.save.mock.calls[storage.save.mock.calls.length - 1];
      const persistedEnvelopes: MarkerSyncEnvelope[] = lastSaveCall[1];
      const acked = persistedEnvelopes.find((e: MarkerSyncEnvelope) => e.id === "mk-1");
      expect(acked?.pendingOpId).toBeUndefined();
    });
  });

  describe("Scenario 2 — Session mismatch ignored", () => {
    it("emits SESSION_MISMATCH_IGNORED when coordinator B acks an op from coordinator A session", () => {
      const storageA = makeStorage();
      const coordinatorA = new MarkerSyncCoordinator({
        clock: makeClock(),
        idGenerator: makeIdGen(["session-A", "mk-1", "op-1"]),
        storage: storageA,
        assetId: "asset-1",
      });
      coordinatorA.setReady(true);
      coordinatorA.add({ timeObservation: { start: 0, end: 5 } }, "track");
      coordinatorA.update("mk-1", { label: "x" }, "track");

      const coordinatorB = new MarkerSyncCoordinator({
        clock: makeClock(),
        idGenerator: makeIdGen(["session-B"]),
        storage: storageA,
        assetId: "asset-1",
      });
      coordinatorB.setReady(true);
      const events: SyncCoordinatorEvent[] = [];
      coordinatorB.on("SESSION_MISMATCH_IGNORED", () => events.push("SESSION_MISMATCH_IGNORED"));

      coordinatorB.acknowledgeCommit("op-1");

      expect(events).toContain("SESSION_MISMATCH_IGNORED");
    });
  });

  describe("Scenario 3 — Failed commit, marker has newer revision — no rollback", () => {
    it("does not rollback when a newer revision exists", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1", "op-A", "op-B"] });
      coordinator.setReady(true);
      const { events, payloads } = collectEvents(coordinator);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track"); // rev=1
      coordinator.update("mk-1", { label: "a" }, "track"); // op-A, rev=2
      coordinator.update("mk-1", { label: "b" }, "track"); // op-B, rev=3

      coordinator.failCommit("op-A"); // op-A revision=2 !== current=3

      expect(events).not.toContain("MARKER_COMMIT_FAILED_ROLLBACK_APPLIED");
      const commitPayloads = payloads["MARKER_COMMIT_REQUESTED"] as any[];
      expect(commitPayloads[commitPayloads.length - 1].revision).toBe(3);
    });
  });

  describe("Scenario 4 — Failed commit, revision unchanged — rollback applied", () => {
    it("rolls back to last confirmed state and persists rollback to storage", () => {
      const { coordinator, storage } = makeCoordinator({ ids: ["session-1", "mk-1", "op-1"] });
      coordinator.setReady(true);
      const { events } = collectEvents(coordinator);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track"); // rev=1
      coordinator.update("mk-1", { label: "changed" }, "track"); // op-1, rev=2

      const saveCountBeforeFail = storage.save.mock.calls.length;
      coordinator.failCommit("op-1"); // op revision=2 === current=2 → rollback

      expect(events).toContain("MARKER_COMMIT_FAILED_ROLLBACK_APPLIED");
      expect(storage.save).toHaveBeenCalledTimes(saveCountBeforeFail + 1);
      const lastSaveCall = storage.save.mock.calls[storage.save.mock.calls.length - 1];
      const persistedEnvelopes: MarkerSyncEnvelope[] = lastSaveCall[1];
      const rolledBack = persistedEnvelopes.find((e: MarkerSyncEnvelope) => e.id === "mk-1");
      expect(rolledBack?.revision).toBe(1);
      expect(rolledBack?.pendingOpId).toBeUndefined();
    });
  });

  describe("Scenario 5 — Rapid drag stream", () => {
    it("emits 10 previews and 1 commit, storage.save called exactly twice", () => {
      const ids = ["session-1", "mk-1", "commit-op"];
      const { coordinator, storage } = makeCoordinator({ ids });
      coordinator.setReady(true);
      const { events } = collectEvents(coordinator);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track");

      for (let i = 0; i < 10; i++) {
        coordinator.preview("mk-1", { timeObservation: { start: i, end: i + 5 } }, "track");
      }
      coordinator.commit("mk-1", "track");

      expect(events.filter((e) => e === "MARKER_PREVIEW_UPDATED")).toHaveLength(10);
      expect(events.filter((e) => e === "MARKER_COMMIT_REQUESTED")).toHaveLength(1);
      expect(storage.save).toHaveBeenCalledTimes(2); // add + commit
    });
  });

  describe("Scenario 6 — Echo suppression", () => {
    it("records source on each update and does not cause infinite loops", () => {
      const { coordinator } = makeCoordinator({
        ids: ["session-1", "mk-1", "op-track", "op-sidebar"],
      });
      coordinator.setReady(true);

      const commitPayloads: any[] = [];
      coordinator.on("MARKER_COMMIT_REQUESTED", (payload) => commitPayloads.push(payload));

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track");
      coordinator.update("mk-1", { label: "from-track" }, "track");

      const lastPayload = commitPayloads[commitPayloads.length - 1];
      if (lastPayload.source !== "sidebar") {
        coordinator.update("mk-1", { label: "from-track" }, "sidebar");
      }

      expect(commitPayloads).toHaveLength(2);
      expect(commitPayloads[0].source).toBe("track");
      expect(commitPayloads[1].source).toBe("sidebar");
    });
  });

  describe("Scenario 7 — Track unavailable (fail-closed)", () => {
    it("emits MARKER_SYSTEM_NOT_READY and returns without mutating state when not ready", () => {
      const { coordinator, storage } = makeCoordinator();
      const { events } = collectEvents(coordinator);

      const result = coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track");

      expect(result).toBeUndefined();
      expect(events).toContain("MARKER_SYSTEM_NOT_READY");
      expect(coordinator.list()).toHaveLength(0);
      expect(storage.save).not.toHaveBeenCalled();
    });
  });

  describe("Scenario 8 — Concurrent updates, higher revision wins", () => {
    it("rejects update with stale expectedRevision", () => {
      const { coordinator } = makeCoordinator({
        ids: ["session-1", "mk-1", "op-sidebar", "op-track"],
      });
      coordinator.setReady(true);
      const { events, payloads } = collectEvents(coordinator);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track"); // rev=1
      coordinator.update("mk-1", { label: "sidebar" }, "sidebar"); // rev=2
      coordinator.update("mk-1", { label: "track" }, "track", 1); // expectedRevision=1, current=2 → rejected

      const commitPayloads = payloads["MARKER_COMMIT_REQUESTED"] as any[];
      expect(commitPayloads).toHaveLength(1);
      expect(commitPayloads[0].revision).toBe(2);
    });
  });

  describe("list() returns MarkerApi[]", () => {
    it("returns marker data objects, not envelopes", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1"] });
      coordinator.setReady(true);

      const added = coordinator.add(
        { timeObservation: { start: 1, end: 10 }, label: "test" },
        "track"
      );
      const markers = coordinator.list();

      expect(markers).toHaveLength(1);
      expect(markers[0]).toEqual(added);
      expect(markers[0].id).toBe("mk-1");
      expect(markers[0].timeObservation).toEqual({ start: 1, end: 10 });
    });
  });

  describe("selected() returns MarkerApi | undefined", () => {
    it("returns undefined when nothing selected", () => {
      const { coordinator } = makeCoordinator();
      coordinator.setReady(true);
      expect(coordinator.selected()).toBeUndefined();
    });

    it("returns the marker object when selected", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1"] });
      coordinator.setReady(true);

      const added = coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track");
      coordinator.select("mk-1");

      expect(coordinator.selected()).toEqual(added);
    });
  });

  describe("clear(source)", () => {
    it("clears all markers and envelopes", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1"] });
      coordinator.setReady(true);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track");
      coordinator.select("mk-1");

      coordinator.clear("track");

      expect(coordinator.list()).toHaveLength(0);
      expect(coordinator.selected()).toBeUndefined();
    });

    it("emits MARKER_SYSTEM_NOT_READY and does nothing when not ready", () => {
      const { coordinator } = makeCoordinator();
      const { events } = collectEvents(coordinator);

      coordinator.clear("track");

      expect(events).toContain("MARKER_SYSTEM_NOT_READY");
      expect(coordinator.list()).toHaveLength(0);
    });
  });

  describe("rollback(opId)", () => {
    it("resolves marker through operation metadata and rolls back envelope", () => {
      const { coordinator, storage } = makeCoordinator({ ids: ["session-1", "mk-1", "op-1"] });
      coordinator.setReady(true);

      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track"); // rev=1
      coordinator.update("mk-1", { label: "changed" }, "track"); // op-1, rev=2

      coordinator.rollback("op-1");

      const lastSaveCall = storage.save.mock.calls[storage.save.mock.calls.length - 1];
      const persistedEnvelopes: MarkerSyncEnvelope[] = lastSaveCall[1];
      const rolledBack = persistedEnvelopes.find((e: MarkerSyncEnvelope) => e.id === "mk-1");
      expect(rolledBack?.revision).toBe(1);

      // Second rollback is a no-op (op already deleted)
      const saveCountAfterRollback = storage.save.mock.calls.length;
      coordinator.rollback("op-1");
      expect(storage.save).toHaveBeenCalledTimes(saveCountAfterRollback);
    });

    it("is a no-op for unknown opId", () => {
      const { coordinator, storage } = makeCoordinator({ ids: ["session-1", "mk-1"] });
      coordinator.setReady(true);
      coordinator.add({ timeObservation: { start: 0, end: 5 } }, "track");

      const saveCountBefore = storage.save.mock.calls.length;
      coordinator.rollback("nonexistent-op");

      expect(storage.save).toHaveBeenCalledTimes(saveCountBefore);
    });

    it("restores marker data visible via list() and selected()", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1", "op-1"] });
      coordinator.setReady(true);

      coordinator.add({ timeObservation: { start: 0, end: 5 }, label: "original" }, "track");
      coordinator.select("mk-1");
      coordinator.update("mk-1", { label: "changed" }, "track"); // op-1

      expect(coordinator.list()[0].label).toBe("changed");
      expect(coordinator.selected()!.label).toBe("changed");

      coordinator.rollback("op-1");

      expect(coordinator.list()[0].label).toBe("original");
      expect(coordinator.selected()!.label).toBe("original");
    });
  });

  describe("update() reflects in list() and selected()", () => {
    it("optimistically applies patch to marker data", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1", "op-1"] });
      coordinator.setReady(true);

      coordinator.add({ timeObservation: { start: 0, end: 5 }, label: "original" }, "track");
      coordinator.select("mk-1");

      coordinator.update("mk-1", { label: "updated" }, "track");

      expect(coordinator.list()[0].label).toBe("updated");
      expect(coordinator.selected()!.label).toBe("updated");
    });
  });

  describe("failCommit() restores marker data via list() and selected()", () => {
    it("rolls back marker to confirmed state after failed commit", () => {
      const { coordinator } = makeCoordinator({ ids: ["session-1", "mk-1", "op-1"] });
      coordinator.setReady(true);

      coordinator.add({ timeObservation: { start: 0, end: 5 }, label: "original" }, "track");
      coordinator.select("mk-1");
      coordinator.update("mk-1", { label: "changed" }, "track"); // op-1, rev=2

      expect(coordinator.list()[0].label).toBe("changed");

      coordinator.failCommit("op-1");

      expect(coordinator.list()[0].label).toBe("original");
      expect(coordinator.selected()!.label).toBe("original");
    });
  });
});
