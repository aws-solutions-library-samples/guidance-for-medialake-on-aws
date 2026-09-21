import { useEffect } from "react";
import type Uppy from "@uppy/core";

/**
 * How often to nudge the Golden Retriever service worker while an upload is pending.
 * Chromium terminates an idle service worker after roughly 30 seconds; the worker keeps
 * the selected file blobs in memory only, so a terminated worker means a refresh restores
 * "ghost" files the user has to re-select. Golden Retriever itself only messages the worker
 * on file add/remove, which is far less often than a long upload lasts.
 */
export const SW_KEEPALIVE_INTERVAL_MS = 20_000;

/**
 * Store name used for the keepalive probe. Golden Retriever's `ServiceWorkerStore` ignores
 * replies for stores it does not own, so probing an unused store is side-effect free.
 */
export const SW_KEEPALIVE_STORE = "medialake-keepalive";

/** Sends one message to the controlling service worker; returns false when there is none. */
export function pingServiceWorker(): boolean {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return false;
  const controller = navigator.serviceWorker.controller;
  if (!controller) return false;
  // `uppy/GET_FILES` is the only Golden Retriever message that is harmless for a store the
  // worker has never seen; anything unknown makes the worker throw.
  controller.postMessage({ type: "uppy/GET_FILES", store: SW_KEEPALIVE_STORE });
  return true;
}

function hasPendingFiles(uppy: Uppy<any, any>): boolean {
  return uppy.getFiles().some((file) => !file.progress.uploadComplete);
}

/**
 * Keeps the Golden Retriever service worker alive for as long as the given Uppy instance
 * holds files that have not finished uploading, so a refresh mid-upload can still recover
 * the blobs (and therefore resume the multipart upload) instead of asking for a re-select.
 */
export function useServiceWorkerKeepalive(uppy: Uppy<any, any> | null): void {
  useEffect(() => {
    if (!uppy) return;
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;

    let timer: ReturnType<typeof setInterval> | null = null;

    const stop = () => {
      if (timer != null) {
        clearInterval(timer);
        timer = null;
      }
    };

    const sync = () => {
      const pending = hasPendingFiles(uppy);
      if (pending && timer == null) {
        pingServiceWorker();
        timer = setInterval(pingServiceWorker, SW_KEEPALIVE_INTERVAL_MS);
      } else if (!pending) {
        stop();
      }
    };

    // Every transition that can change whether something is still pending.
    const events = [
      "files-added",
      "file-removed",
      "upload-success",
      "complete",
      "cancel-all",
      "restored",
    ] as const;
    events.forEach((event) => uppy.on(event as any, sync));
    sync();

    return () => {
      events.forEach((event) => uppy.off(event as any, sync));
      stop();
    };
  }, [uppy]);
}

export default useServiceWorkerKeepalive;
