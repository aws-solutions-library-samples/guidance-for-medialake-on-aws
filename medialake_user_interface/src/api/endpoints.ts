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
    PERMISSION_SETS: {
        BASE: '/authorization/permission-sets',
        GET: (id: string) => `/authorization/permission-sets/${id}`,
        UPDATE: (id: string) => `/authorization/permission-sets/${id}`,
        DELETE: (id: string) => `/authorization/permission-sets/${id}`,
    },
    GROUPS: {
        BASE: '/authorization/groups',
        GET: (id: string) => `/authorization/groups/${id}`,
        UPDATE: (id: string) => `/authorization/groups/${id}`,
        DELETE: (id: string) => `/authorization/groups/${id}`,
        ADD_MEMBERS: (id: string) => `/authorization/groups/${id}/members`,
        REMOVE_MEMBER: (groupId: string, userId: string) => `/authorization/groups/${groupId}/members/${userId}`,
    },
    ASSIGNMENTS: {
        USER: {
            BASE: (userId: string) => `/authorization/assignments/users/${userId}`,
            REMOVE: (userId: string, permissionSetId: string) =>
                `/authorization/assignments/users/${userId}/permission-sets/${permissionSetId}`,
        },
        GROUP: {
            BASE: (groupId: string) => `/authorization/assignments/groups/${groupId}`,
            REMOVE: (groupId: string, permissionSetId: string) =>
                `/authorization/assignments/groups/${groupId}/permission-sets/${permissionSetId}`,
        },
    },
    DISABLE_USER: (userId: string) => `/users/user/${userId}/disableuser`,
    ENABLE_USER: (userId: string) => `/users/user/${userId}/enableuser`,
    SYSTEM_SETTINGS: {
        GET: '/settings/system',
        SEARCH: '/settings/system/search'
    },
    FAVORITES: {
        BASE: '/users/favorites',
        DELETE: (itemType: string, itemId: string) => `/users/favorites/${itemType}/${itemId}`
    }
};
