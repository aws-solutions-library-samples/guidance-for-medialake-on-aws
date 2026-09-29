import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/queryKeys";
import { useDomainActions, useSearchStore } from "@/stores/searchStore";
import {
  canonicalJson,
  definitionToSearchParams,
  fingerprintDefinition,
  isBlankDefinition,
  normalizeDefinition,
  resolveRelativeDates,
  SEARCH_MODES_PARAM,
  SEMANTIC_MODE_PARAM,
  type SearchDefinition,
} from "./searchDefinition";
import {
  useRecordSearch,
  useSavedSearches,
  useSearchHistory,
  type SavedSearch,
  type SearchHistoryEntry,
} from "./api";

/** How long results must stay on screen before the search counts as "run". */
export const RECORD_AFTER_MS = 2000;

/**
 * Run a stored search: put its options into the search store, then navigate
 * to the /search URL that reproduces it. Relative date ranges are resolved
 * against "now" first.
 */
export function useRunSearch() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setQuery, setIsSemantic, setSemanticMode, setSearchModes, setFilters } =
    useDomainActions();

  return useCallback(
    (definition: SearchDefinition) => {
      const resolved = resolveRelativeDates(normalizeDefinition(definition));
      setQuery(resolved.q);
      setIsSemantic(resolved.semantic);
      if (resolved.semantic) {
        if (resolved.semanticMode) setSemanticMode(resolved.semanticMode);
        if (resolved.searchModes?.length) setSearchModes(resolved.searchModes);
      }
      setFilters(resolved.filters ?? {});
      // Re-running an identical search must still fetch fresh results.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.SEARCH.lists() });
      navigate(`/search?${definitionToSearchParams(resolved).toString()}`);
    },
    [navigate, queryClient, setQuery, setIsSemantic, setSemanticMode, setSearchModes, setFilters]
  );
}

/**
 * Record the search on screen once its results have settled.
 *
 * Recording here, rather than in the search box, captures every way a search
 * can be run (typing and pausing, Enter, applying filters, replaying a recent
 * or saved search) in one place, and skips the intermediate searches the box
 * fires while someone is still typing: each new search restarts the timer.
 */
export function useRecordSearchOnSettle(
  definition: SearchDefinition,
  { settled, delayMs = RECORD_AFTER_MS }: { settled: boolean; delayMs?: number }
) {
  const record = useRecordSearch();
  const recordRef = useRef(record.mutate);
  recordRef.current = record.mutate;
  const lastRecorded = useRef<string | null>(null);
  const key = canonicalJson(normalizeDefinition(definition));

  useEffect(() => {
    if (!settled || key === lastRecorded.current) return;
    const normalized = normalizeDefinition(definition);
    if (isBlankDefinition(normalized)) return;
    const timer = window.setTimeout(() => {
      lastRecorded.current = key;
      recordRef.current(normalized);
    }, delayMs);
    return () => window.clearTimeout(timer);
    // `definition` is represented by `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, settled, delayMs]);
}

/**
 * Keep the semantic options (Full/Clip and the Visual/Audio/Transcript modes)
 * in the /search URL, so a copied link or a replayed search reproduces the
 * exact results. The URL wins on load (see useSearchState); after that, toggling
 * an option in the search bar rewrites the URL in place.
 */
export function useSemanticOptionsInUrl(
  searchParams: URLSearchParams,
  setSearchParams: (next: URLSearchParams, options?: { replace?: boolean }) => void
) {
  const semanticMode = useSearchStore((s) => s.semanticMode);
  const searchModes = useSearchStore((s) => s.searchModes);
  const paramsRef = useRef(searchParams);
  paramsRef.current = searchParams;

  useEffect(() => {
    // Read the latest store state: the URL -> store sync may have run in this
    // same commit, after this render captured its values.
    const state = useSearchStore.getState();
    const params = new URLSearchParams(paramsRef.current);
    if (params.get("semantic") !== "true") return;

    const wantedModes = [...state.searchModes].sort().join(",");
    if (
      params.get(SEMANTIC_MODE_PARAM) === state.semanticMode &&
      params.get(SEARCH_MODES_PARAM) === wantedModes
    ) {
      return;
    }
    params.set(SEMANTIC_MODE_PARAM, state.semanticMode);
    if (wantedModes) params.set(SEARCH_MODES_PARAM, wantedModes);
    else params.delete(SEARCH_MODES_PARAM);
    setSearchParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [semanticMode, searchModes]);
}

/** Fingerprint of a definition, computed asynchronously (Web Crypto). */
export function useFingerprint(definition: SearchDefinition | null): string | null {
  const [fingerprint, setFingerprint] = useState<string | null>(null);
  const key = definition ? canonicalJson(normalizeDefinition(definition)) : null;
  useEffect(() => {
    let cancelled = false;
    if (!definition) {
      setFingerprint(null);
      return;
    }
    fingerprintDefinition(definition).then((fp) => {
      if (!cancelled) setFingerprint(fp);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return fingerprint;
}

/** The saved search matching this definition, if the user has saved it. */
export function useMatchingSavedSearch(definition: SearchDefinition | null) {
  const fingerprint = useFingerprint(definition);
  const saved = useSavedSearches();
  const match = useMemo(
    () => (fingerprint ? saved.data?.find((s) => s.fingerprint === fingerprint) : undefined),
    [fingerprint, saved.data]
  );
  return { match, isReady: !!fingerprint && !saved.isLoading };
}

export type SuggestionItem =
  | { kind: "saved"; id: string; definition: SearchDefinition; saved: SavedSearch }
  | { kind: "history"; id: string; definition: SearchDefinition; entry: SearchHistoryEntry };

export const MAX_SAVED_IN_DROPDOWN = 5;

/**
 * Items for the search box dropdown: saved searches first (they are what the
 * user deliberately kept), then recent searches. Typing filters both.
 */
export function useSearchSuggestions(filterText: string) {
  const history = useSearchHistory();
  const saved = useSavedSearches();

  return useMemo(() => {
    const needle = filterText.trim().toLowerCase();
    const matches = (...texts: string[]) =>
      !needle || texts.some((text) => text.toLowerCase().includes(needle));

    const savedItems: SuggestionItem[] = (saved.data ?? [])
      .filter((s) => matches(s.name, s.definition.q))
      .slice(0, MAX_SAVED_IN_DROPDOWN)
      .map((s) => ({ kind: "saved", id: `saved-${s.id}`, definition: s.definition, saved: s }));

    const historyItems: SuggestionItem[] = (history.data ?? [])
      .filter((e) => matches(e.definition.q))
      .map((e) => ({
        kind: "history",
        id: `history-${e.fingerprint}`,
        definition: e.definition,
        entry: e,
      }));

    return {
      savedItems,
      historyItems,
      items: [...savedItems, ...historyItems],
      totalSaved: saved.data?.length ?? 0,
      hasAny: (saved.data?.length ?? 0) + (history.data?.length ?? 0) > 0,
    };
  }, [filterText, history.data, saved.data]);
}
