export const QUERY_KEYS = {
    CONNECTORS: {
        all: ['connectors'] as const,
        lists: () => [...QUERY_KEYS.CONNECTORS.all, 'list'] as const,
        list: (filters: string) => [...QUERY_KEYS.CONNECTORS.lists(), { filters }] as const,
        details: () => [...QUERY_KEYS.CONNECTORS.all, 'detail'] as const,
        detail: (id: string) => [...QUERY_KEYS.CONNECTORS.details(), id] as const,
        s3: {
            all: ['connectors', 's3'] as const,
            buckets: () => [...QUERY_KEYS.CONNECTORS.s3.all, 'buckets'] as const,
            explorer: (connectorId: string, prefix: string, continuationToken: string | null) =>
                [...QUERY_KEYS.CONNECTORS.s3.all, 'explorer', connectorId, prefix, continuationToken] as const,
        },
    },
    SEARCH: {
        all: ['search'] as const,
    },
    ASSETS: {
        all: ['assets'] as const,
        lists: () => [...QUERY_KEYS.ASSETS.all, 'list'] as const,
        list: (filters: string) => [...QUERY_KEYS.ASSETS.lists(), { filters }] as const,
        details: () => [...QUERY_KEYS.ASSETS.all, 'detail'] as const,
        detail: (id: string) => [...QUERY_KEYS.ASSETS.details(), id] as const,
    },
    USERS: {
        all: ['users'] as const,
        lists: () => [...QUERY_KEYS.USERS.all, 'list'] as const,
        list: (filters: string) => [...QUERY_KEYS.USERS.lists(), { filters }] as const,
        details: () => [...QUERY_KEYS.USERS.all, 'detail'] as const,
        detail: (id: string) => [...QUERY_KEYS.USERS.details(), id] as const,
    },
    ROLES: {
        all: ['roles'] as const,
        lists: () => [...QUERY_KEYS.ROLES.all, 'list'] as const,
        list: (filters: string) => [...QUERY_KEYS.ROLES.lists(), { filters }] as const,
        details: () => [...QUERY_KEYS.ROLES.all, 'detail'] as const,
        detail: (id: string) => [...QUERY_KEYS.ROLES.details(), id] as const,
    },
} as const;
