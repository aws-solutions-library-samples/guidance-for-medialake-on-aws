/**
 * Data hooks for search history and saved searches.
 *
 * Both lists belong to the signed-in user; the API derives the user from the
 * token. Reads are strongly consistent server-side, so mutations patch the
 * cache optimistically and then reconcile with the server's answer, the same
 * approach `useFavorites` takes.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSnackbar } from "notistack";
import { useTranslation } from "react-i18next";
import { apiClient } from "@/api/apiClient";
import { API_ENDPOINTS } from "@/api/endpoints";
import { QUERY_KEYS } from "@/api/queryKeys";
import { logger } from "@/common/helpers/logger";
import type { SearchDefinition } from "./searchDefinition";

export interface SearchHistoryEntry {
  fingerprint: string;
  definition: SearchDefinition;
  searchedAt: string;
}

export interface SavedSearch {
  id: string;
  name: string;
  definition: SearchDefinition;
  fingerprint: string;
  createdAt: string;
  updatedAt: string;
}

interface Envelope<T> {
  status: string;
  message?: string;
  data: T;
}

interface HistoryPayload {
  items: SearchHistoryEntry[];
  limit: number;
}

interface SavedListPayload {
  items: SavedSearch[];
  count: number;
  limit: number;
}

type SavedCreatePayload = SavedSearch & { existing: boolean };

/** The API's error message, for showing to the user. */
export function apiErrorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { message?: string } } })?.response?.data
    ?.message;
  return typeof message === "string" && message ? message : fallback;
}

// ─── Search history ──────────────────────────────────────────────────────────

export const useSearchHistory = (enabled = true) =>
  useQuery<SearchHistoryEntry[], Error>({
    queryKey: QUERY_KEYS.SEARCH_HISTORY.all,
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.get<Envelope<HistoryPayload>>(
        API_ENDPOINTS.SEARCH_HISTORY.BASE,
        // A 403 must not eject the user from the page they are on.
        { signal, skipAccessDeniedRedirect: true } as never
      );
      return data?.data?.items ?? [];
    },
    enabled,
    staleTime: 60 * 1000,
    gcTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: false,
  });

/**
 * Record a committed search. Fire-and-forget: history is a convenience, so a
 * failure is logged and never surfaced to the user.
 */
export const useRecordSearch = () => {
  const queryClient = useQueryClient();
  return useMutation<SearchHistoryEntry[], Error, SearchDefinition>({
    mutationFn: async (definition) => {
      const { data } = await apiClient.post<Envelope<HistoryPayload>>(
        API_ENDPOINTS.SEARCH_HISTORY.BASE,
        { definition }
      );
      return data?.data?.items ?? [];
    },
    onSuccess: (items) => {
      queryClient.setQueryData(QUERY_KEYS.SEARCH_HISTORY.all, items);
    },
    onError: (error) => logger.warn("Failed to record search history", error),
  });
};

interface HistoryContext {
  previous?: SearchHistoryEntry[];
}

export const useRemoveHistoryEntry = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();
  return useMutation<SearchHistoryEntry[], Error, string, HistoryContext>({
    mutationFn: async (fingerprint) => {
      const { data } = await apiClient.delete<Envelope<HistoryPayload>>(
        API_ENDPOINTS.SEARCH_HISTORY.ENTRY(fingerprint)
      );
      return data?.data?.items ?? [];
    },
    onMutate: async (fingerprint) => {
      const key = QUERY_KEYS.SEARCH_HISTORY.all;
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<SearchHistoryEntry[]>(key);
      queryClient.setQueryData<SearchHistoryEntry[]>(
        key,
        (previous ?? []).filter((e) => e.fingerprint !== fingerprint)
      );
      return { previous };
    },
    onSuccess: (items) => queryClient.setQueryData(QUERY_KEYS.SEARCH_HISTORY.all, items),
    onError: (_error, _fp, context) => {
      queryClient.setQueryData(QUERY_KEYS.SEARCH_HISTORY.all, context?.previous);
      enqueueSnackbar(t("search.history.removeFailed", "Couldn't remove that search"), {
        variant: "error",
        autoHideDuration: 5000,
      });
    },
  });
};

export const useClearSearchHistory = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();
  return useMutation<void, Error, void, HistoryContext>({
    mutationFn: async () => {
      await apiClient.delete(API_ENDPOINTS.SEARCH_HISTORY.BASE);
    },
    onMutate: async () => {
      const key = QUERY_KEYS.SEARCH_HISTORY.all;
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<SearchHistoryEntry[]>(key);
      queryClient.setQueryData<SearchHistoryEntry[]>(key, []);
      return { previous };
    },
    onError: (_error, _vars, context) => {
      queryClient.setQueryData(QUERY_KEYS.SEARCH_HISTORY.all, context?.previous);
      enqueueSnackbar(t("search.history.clearFailed", "Couldn't clear your search history"), {
        variant: "error",
        autoHideDuration: 5000,
      });
    },
  });
};

// ─── Saved searches ──────────────────────────────────────────────────────────

export const useSavedSearches = (enabled = true) =>
  useQuery<SavedSearch[], Error>({
    queryKey: QUERY_KEYS.SAVED_SEARCHES.all,
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.get<Envelope<SavedListPayload>>(
        API_ENDPOINTS.SAVED_SEARCHES.BASE,
        // A 403 must not eject the user from the page they are on.
        { signal, skipAccessDeniedRedirect: true } as never
      );
      return data?.data?.items ?? [];
    },
    enabled,
    staleTime: 60 * 1000,
    gcTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: false,
  });

const upsertSaved = (list: SavedSearch[] | undefined, item: SavedSearch): SavedSearch[] => [
  item,
  ...(list ?? []).filter((s) => s.id !== item.id),
];

export const useCreateSavedSearch = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();
  return useMutation<SavedCreatePayload, Error, { name: string; definition: SearchDefinition }>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<Envelope<SavedCreatePayload>>(
        API_ENDPOINTS.SAVED_SEARCHES.BASE,
        body
      );
      return data.data;
    },
    onSuccess: (saved) => {
      queryClient.setQueryData<SavedSearch[]>(QUERY_KEYS.SAVED_SEARCHES.all, (list) =>
        saved.existing ? list : upsertSaved(list, saved)
      );
      enqueueSnackbar(
        saved.existing
          ? t("search.saved.alreadySaved", "This search is already saved as “{{name}}”", {
              name: saved.name,
            })
          : t("search.saved.saved", "Search saved"),
        { variant: saved.existing ? "info" : "success", autoHideDuration: 3000 }
      );
    },
    onError: (error) => {
      enqueueSnackbar(
        apiErrorMessage(error, t("search.saved.saveFailed", "Couldn't save this search")),
        { variant: "error", autoHideDuration: 5000 }
      );
    },
  });
};

interface SavedContext {
  previous?: SavedSearch[];
}

export const useRenameSavedSearch = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();
  return useMutation<SavedSearch, Error, { id: string; name: string }, SavedContext>({
    mutationFn: async ({ id, name }) => {
      const { data } = await apiClient.patch<Envelope<SavedSearch>>(
        API_ENDPOINTS.SAVED_SEARCHES.ITEM(id),
        { name }
      );
      return data.data;
    },
    onMutate: async ({ id, name }) => {
      const key = QUERY_KEYS.SAVED_SEARCHES.all;
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<SavedSearch[]>(key);
      queryClient.setQueryData<SavedSearch[]>(key, (list) =>
        (list ?? []).map((s) => (s.id === id ? { ...s, name } : s))
      );
      return { previous };
    },
    onSuccess: (saved) =>
      queryClient.setQueryData<SavedSearch[]>(QUERY_KEYS.SAVED_SEARCHES.all, (list) =>
        upsertSaved(list, saved)
      ),
    onError: (error, _vars, context) => {
      queryClient.setQueryData(QUERY_KEYS.SAVED_SEARCHES.all, context?.previous);
      enqueueSnackbar(
        apiErrorMessage(error, t("search.saved.renameFailed", "Couldn't rename this search")),
        { variant: "error", autoHideDuration: 5000 }
      );
    },
  });
};

export const useDeleteSavedSearch = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();
  return useMutation<void, Error, string, SavedContext>({
    mutationFn: async (id) => {
      await apiClient.delete(API_ENDPOINTS.SAVED_SEARCHES.ITEM(id));
    },
    onMutate: async (id) => {
      const key = QUERY_KEYS.SAVED_SEARCHES.all;
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<SavedSearch[]>(key);
      queryClient.setQueryData<SavedSearch[]>(key, (list) =>
        (list ?? []).filter((s) => s.id !== id)
      );
      return { previous };
    },
    onError: (_error, _id, context) => {
      queryClient.setQueryData(QUERY_KEYS.SAVED_SEARCHES.all, context?.previous);
      enqueueSnackbar(t("search.saved.deleteFailed", "Couldn't delete this saved search"), {
        variant: "error",
        autoHideDuration: 5000,
      });
    },
  });
};
