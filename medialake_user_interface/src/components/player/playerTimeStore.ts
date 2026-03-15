/**
 * playerTimeStore — Zustand store for high-frequency player time values.
 *
 * Avoids React re-renders by storing currentTime outside of React state.
 * Components that need the latest time for imperative actions (e.g., adding
 * a marker at the current position) read from the store without subscribing
 * to updates. Components that need to display time can subscribe selectively.
 */
import { createStore } from "zustand/vanilla";

export interface PlayerTimeState {
  currentTime: number;
  duration: number;
  setCurrentTime: (time: number) => void;
  setDuration: (duration: number) => void;
}

export const playerTimeStore = createStore<PlayerTimeState>((set) => ({
  currentTime: 0,
  duration: 0,
  setCurrentTime: (currentTime) => set({ currentTime }),
  setDuration: (duration) => set({ duration }),
}));

/** Read current time without subscribing (no re-render). */
export function getPlayerCurrentTime(): number {
  return playerTimeStore.getState().currentTime;
}

/** Read duration without subscribing (no re-render). */
export function getPlayerDuration(): number {
  return playerTimeStore.getState().duration;
}
