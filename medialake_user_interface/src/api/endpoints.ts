// src/api/endpoints.ts

export const API_ENDPOINTS = {
    CONNECTORS: '/connectors',
    PIPELINES: "/pipelines",
    PIPELINE_EXECUTIONS: "/pipelines/executions",
    SEARCH: "/search",
    ASSETS: {
        GET: (id: string) => `/assets/${id}`,
        DELETE: (id: string) => `/assets/${id}`,
        RENAME: (id: string) => `/assets/${id}/rename`,
    },
    USERS: '/settings/users',
    USER: '/users/user',
    ROLES: '/settings/roles',
    DISABLE_USER: (userId: string) => `/users/user/${userId}/disableuser`,
    ENABLE_USER: (userId: string) => `/users/user/${userId}/enableuser`,
    SYSTEM_SETTINGS: {
        GET: '/settings/system',
        SEARCH: '/settings/system/search'
    }
};
