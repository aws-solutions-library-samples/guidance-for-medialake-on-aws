/**
 * Golden Retriever service worker.
 *
 * Holds references to files the user selected for upload so they survive a page refresh or
 * an accidentally closed tab. IndexedDB only keeps files up to a few MiB each; anything
 * larger is only recoverable through this worker (and only until the worker itself is
 * evicted — it does not survive a browser restart). It caches nothing else and intercepts
 * no requests.
 *
 * Built as its own Vite entry so it lands at `/sw.js` (see `vite.config.ts`) and registered
 * from `src/main.tsx` with `{ type: "module" }`.
 */
import "@uppy/golden-retriever/lib/ServiceWorker.js";
