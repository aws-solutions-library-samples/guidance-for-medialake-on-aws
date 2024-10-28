export const QUERY_KEYS = {
    USERS: 'users',
    POSTS: 'posts',
    COMMENTS: 'comments',
    CONNECTORS: {
        all: ['connectors'] as const,
        lists: () => [...QUERY_KEYS.CONNECTORS.all, 'list'] as const,
        list: (filters: string) => [...QUERY_KEYS.CONNECTORS.lists(), { filters }] as const,
        details: () => [...QUERY_KEYS.CONNECTORS.all, 'detail'] as const,
        detail: (id: string) => [...QUERY_KEYS.CONNECTORS.details(), id] as const,
        s3: {
            all: ['connectors', 's3'] as const,
            buckets: () => [...QUERY_KEYS.CONNECTORS.s3.all, 'buckets'] as const,
        },
    },
    S3_LIST: 's3list'
} as const;
