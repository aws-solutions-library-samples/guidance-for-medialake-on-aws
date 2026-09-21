import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import Uppy from "@uppy/core";
import {
  SW_KEEPALIVE_INTERVAL_MS,
  SW_KEEPALIVE_STORE,
  pingServiceWorker,
  useServiceWorkerKeepalive,
} from "./useServiceWorkerKeepalive";

const postMessage = vi.fn();

function installServiceWorker(controller: { postMessage: typeof postMessage } | null) {
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { controller },
  });
}

function addFile(uppy: Uppy<any, any>, name = "clip.mp4") {
  return uppy.addFile({
    name,
    type: "video/mp4",
    data: new Blob([new Uint8Array(16)], { type: "video/mp4" }),
    source: "test",
  });
}

describe("pingServiceWorker", () => {
  afterEach(() => {
    postMessage.mockReset();
    // @ts-expect-error cleanup of the test double
    delete navigator.serviceWorker;
  });

  it("sends a Golden Retriever GET_FILES probe for an unused store", () => {
    installServiceWorker({ postMessage });
    expect(pingServiceWorker()).toBe(true);
    expect(postMessage).toHaveBeenCalledWith({
      type: "uppy/GET_FILES",
      store: SW_KEEPALIVE_STORE,
    });
  });

  it("is a no-op when no worker controls the page", () => {
    installServiceWorker(null);
    expect(pingServiceWorker()).toBe(false);
    expect(postMessage).not.toHaveBeenCalled();
  });
});

describe("useServiceWorkerKeepalive", () => {
  let uppy: Uppy<any, any>;

  beforeEach(() => {
    vi.useFakeTimers();
    installServiceWorker({ postMessage });
    uppy = new Uppy({ id: "keepalive-test", autoProceed: false });
  });

  afterEach(() => {
    postMessage.mockReset();
    vi.useRealTimers();
    // @ts-expect-error cleanup of the test double
    delete navigator.serviceWorker;
  });

  it("does nothing while the instance holds no files", () => {
    renderHook(() => useServiceWorkerKeepalive(uppy));
    act(() => {
      vi.advanceTimersByTime(SW_KEEPALIVE_INTERVAL_MS * 3);
    });
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("pings on a schedule while a file is pending and stops once it is removed", () => {
    renderHook(() => useServiceWorkerKeepalive(uppy));

    let fileId = "";
    act(() => {
      fileId = addFile(uppy);
    });
    // One immediate ping, then one per interval.
    expect(postMessage).toHaveBeenCalledTimes(1);
    act(() => {
      vi.advanceTimersByTime(SW_KEEPALIVE_INTERVAL_MS * 2);
    });
    expect(postMessage).toHaveBeenCalledTimes(3);

    act(() => {
      uppy.removeFile(fileId);
    });
    act(() => {
      vi.advanceTimersByTime(SW_KEEPALIVE_INTERVAL_MS * 2);
    });
    expect(postMessage).toHaveBeenCalledTimes(3);
  });

  it("stops pinging when the pending file finishes uploading", () => {
    renderHook(() => useServiceWorkerKeepalive(uppy));
    let fileId = "";
    act(() => {
      fileId = addFile(uppy);
    });
    expect(postMessage).toHaveBeenCalledTimes(1);

    act(() => {
      uppy.setFileState(fileId, {
        progress: { ...uppy.getFile(fileId).progress, uploadComplete: true },
      });
      uppy.emit("upload-success", uppy.getFile(fileId), { status: 200 });
    });
    act(() => {
      vi.advanceTimersByTime(SW_KEEPALIVE_INTERVAL_MS * 2);
    });
    expect(postMessage).toHaveBeenCalledTimes(1);
  });

  it("clears the timer on unmount", () => {
    const { unmount } = renderHook(() => useServiceWorkerKeepalive(uppy));
    act(() => {
      addFile(uppy);
    });
    expect(postMessage).toHaveBeenCalledTimes(1);
    unmount();
    act(() => {
      vi.advanceTimersByTime(SW_KEEPALIVE_INTERVAL_MS * 2);
    });
    expect(postMessage).toHaveBeenCalledTimes(1);
  });

  it("does not subscribe when no Uppy instance is provided", () => {
    renderHook(() => useServiceWorkerKeepalive(null));
    act(() => {
      vi.advanceTimersByTime(SW_KEEPALIVE_INTERVAL_MS);
    });
    expect(postMessage).not.toHaveBeenCalled();
  });
});
