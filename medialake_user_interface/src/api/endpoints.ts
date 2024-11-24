// src/api/endpoints.ts

export const API_ENDPOINTS = {
    CONNECTORS: '/connectors',
    PIPELINES: "/pipelines",
    SEARCH: "/search",
    ASSETS: {
        GET: (id: string) => `/assets/${id}`,
        DELETE: (id: string) => `/assets/${id}`,
        RENAME: (id: string) => `/assets/${id}/rename`,
    },
    USERS: '/settings/users',
    USER: '/settings/users/user',
    ROLES: '/settings/roles'
};
