import { createQueryKeyStore } from "@lukemorales/query-key-factory";

export const queryKeys = createQueryKeyStore({
  users: {
    root: ["users"],
    lists: null,
    list: (filters: string) => ({
      queryKey: ["users", "list", { filters }],
    }),
    details: null,
    detail: (id: string) => ({
      queryKey: ["users", "detail", id],
    }),
  },
  connectors: {
    root: ["connectors"],
    lists: null,
    list: (filters: string) => ({
      queryKey: ["connectors", "list", { filters }],
    }),
    details: null,
    detail: (id: string) => ({
      queryKey: ["connectors", "detail", id],
    }),
  },
  connectorS3: {
    root: ["connectors", "s3"],
    buckets: null,
    explorer: (
      connectorId: string,
      prefix: string,
      continuationToken: string | null,
    ) => ({
      queryKey: [
        "connectors",
        "s3",
        "explorer",
        connectorId,
        prefix,
        continuationToken,
      ],
    }),
  },
  pipelines: {
    root: ["pipelines"],
    lists: null,
    list: (filters: string) => ({
      queryKey: ["pipelines", "list", { filters }],
    }),
    details: null,
    detail: (id: string) => ({
      queryKey: ["pipelines", "detail", id],
    }),
  },
  pipelineExecutions: {
    root: ["pipeline-executions"],
    lists: null,
    list: (page: number, pageSize: number, filters?: Record<string, any>) => ({
      queryKey: ["pipeline-executions", "list", { page, pageSize, filters }],
    }),
    details: null,
    detail: (id: string) => ({
      queryKey: ["pipeline-executions", "detail", id],
    }),
  },
  search: {
    root: ["search"],
  },
  assets: {
    root: ["assets"],
    lists: null,
    list: (filters: string) => ({
      queryKey: ["assets", "list", { filters }],
    }),
    details: null,
    detail: (id: string) => ({
      queryKey: ["assets", "detail", id],
    }),
  },
  roles: {
    root: ["roles"],
    lists: null,
    list: (filters: string) => ({
      queryKey: ["roles", "list", { filters }],
    }),
    details: null,
    detail: (id: string) => ({
      queryKey: ["roles", "detail", id],
    }),
  },
  environments: {
    root: ["environments"],
    lists: null,
    list: (filters: string) => ({
      queryKey: ["environments", "list", { filters }],
    }),
    details: null,
    detail: (id: string) => ({
      queryKey: ["environments", "detail", id],
    }),
  },
});
