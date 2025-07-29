export const QUERY_KEYS = {
  CONNECTORS: {
    all: ["connectors"] as const,
    lists: () => [...QUERY_KEYS.CONNECTORS.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.CONNECTORS.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.CONNECTORS.all, "detail"] as const,
    detail: (id: string) => [...QUERY_KEYS.CONNECTORS.details(), id] as const,
    assets: (
      connectorId: string,
      page: number,
      pageSize: number,
      sortBy: string,
      sortDirection: string,
      assetType?: string,
      searchTerm?: string,
      bucketName?: string,
    ) =>
      [
        ...QUERY_KEYS.CONNECTORS.all,
        "assets",
        connectorId,
        {
          page,
          pageSize,
          sortBy,
          sortDirection,
          assetType,
          searchTerm,
          bucketName,
        },
      ] as const,
    s3: {
      all: ["connectors", "s3"] as const,
      buckets: () => [...QUERY_KEYS.CONNECTORS.s3.all, "buckets"] as const,
      explorer: (
        connectorId: string,
        prefix: string,
        continuationToken: string | null,
      ) =>
        [
          ...QUERY_KEYS.CONNECTORS.s3.all,
          "explorer",
          connectorId,
          prefix,
          continuationToken,
        ] as const,
    },
  },

  PIPELINES: {
    all: ["pipelines"] as const,
    lists: () => [...QUERY_KEYS.PIPELINES.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.PIPELINES.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.PIPELINES.all, "detail"] as const,
    detail: (id: string) => [...QUERY_KEYS.PIPELINES.details(), id] as const,
  },

  PIPELINE_EXECUTIONS: {
    all: ["pipeline-executions"] as const,
    lists: () => [...QUERY_KEYS.PIPELINE_EXECUTIONS.all, "list"] as const,
    list: (page: number, pageSize: number, filters?: Record<string, any>) =>
      [
        ...QUERY_KEYS.PIPELINE_EXECUTIONS.lists(),
        { page, pageSize, filters },
      ] as const,
    details: () => [...QUERY_KEYS.PIPELINE_EXECUTIONS.all, "detail"] as const,
    detail: (id: string) =>
      [...QUERY_KEYS.PIPELINE_EXECUTIONS.details(), id] as const,
  },
  SEARCH: {
    all: ["search"] as const,
    lists: () => [...QUERY_KEYS.SEARCH.all, "list"] as const,
    list: (
      query: string,
      page: number,
      pageSize: number,
      isSemantic: boolean,
      fields?: string[],
      facetParams?: Record<string, any>,
    ) =>
      [
        ...QUERY_KEYS.SEARCH.lists(),
        { query, page, pageSize, isSemantic, fields, facetParams },
      ] as const,
    fields: () => [...QUERY_KEYS.SEARCH.all, "fields"] as const,
  },
  ASSETS: {
    all: ["assets"] as const,
    lists: () => [...QUERY_KEYS.ASSETS.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.ASSETS.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.ASSETS.all, "detail"] as const,
    detail: (id: string) => [...QUERY_KEYS.ASSETS.details(), id] as const,
  },
  USERS: {
    all: ["users"] as const,
    lists: () => [...QUERY_KEYS.USERS.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.USERS.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.USERS.all, "detail"] as const,
    detail: (id: string) => [...QUERY_KEYS.USERS.details(), id] as const,
  },
  FAVORITES: {
    all: ["favorites"] as const,
    lists: () => [...QUERY_KEYS.FAVORITES.all, "list"] as const,
    list: (itemType?: string) =>
      [...QUERY_KEYS.FAVORITES.lists(), { itemType }] as const,
  },
  ROLES: {
    all: ["roles"] as const,
    lists: () => [...QUERY_KEYS.ROLES.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.ROLES.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.ROLES.all, "detail"] as const,
    detail: (id: string) => [...QUERY_KEYS.ROLES.details(), id] as const,
  },
  PERMISSION_SETS: {
    all: ["permission-sets"] as const,
    lists: () => [...QUERY_KEYS.PERMISSION_SETS.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.PERMISSION_SETS.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.PERMISSION_SETS.all, "detail"] as const,
    detail: (id: string) =>
      [...QUERY_KEYS.PERMISSION_SETS.details(), id] as const,
  },
  GROUPS: {
    all: ["groups"] as const,
    lists: () => [...QUERY_KEYS.GROUPS.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.GROUPS.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.GROUPS.all, "detail"] as const,
    detail: (id: string) => [...QUERY_KEYS.GROUPS.details(), id] as const,
    members: (id: string) =>
      [...QUERY_KEYS.GROUPS.detail(id), "members"] as const,
  },
  ASSIGNMENTS: {
    user: {
      all: (userId: string) => ["assignments", "user", userId] as const,
      list: (userId: string) =>
        [...QUERY_KEYS.ASSIGNMENTS.user.all(userId), "list"] as const,
    },
    group: {
      all: (groupId: string) => ["assignments", "group", groupId] as const,
      list: (groupId: string) =>
        [...QUERY_KEYS.ASSIGNMENTS.group.all(groupId), "list"] as const,
    },
  },
  ENVIRONMENTS: {
    all: ["environments"] as const,
    lists: () => [...QUERY_KEYS.ENVIRONMENTS.all, "list"] as const,
    list: (filters: string) =>
      [...QUERY_KEYS.ENVIRONMENTS.lists(), { filters }] as const,
    details: () => [...QUERY_KEYS.ENVIRONMENTS.all, "detail"] as const,
    detail: (id: string) => [...QUERY_KEYS.ENVIRONMENTS.details(), id] as const,
  },
  SYSTEM_SETTINGS: {
    all: ["system-settings"] as const,
    search: () => [...QUERY_KEYS.SYSTEM_SETTINGS.all, "search"] as const,
  },
} as const;
