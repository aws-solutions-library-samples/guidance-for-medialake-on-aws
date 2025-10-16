// src/api/endpoints.ts

export const API_ENDPOINTS = {
  CONNECTORS: "/connectors",
  PIPELINES: "/pipelines",
  PIPELINE_EXECUTIONS: "/pipelines/executions",
  PIPELINE_EXECUTION_RETRY: {
    FROM_CURRENT: (id: string) =>
      `/pipelines/executions/${id}/retry?type=from_current`,
    FROM_START: (id: string) =>
      `/pipelines/executions/${id}/retry?type=from_start`,
    BASE: (id: string) => `/pipelines/executions/${id}/retry`,
  },
  SEARCH: "/search",
  ASSETS: {
    GET: (id: string) => `/assets/${id}`,
    DELETE: (id: string) => `/assets/${id}`,
    RENAME: (id: string) => `/assets/${id}/rename`,
    UPLOAD: "/assets/upload",
    BULK_DOWNLOAD: "/assets/download/bulk",
    BULK_DOWNLOAD_USER_JOBS: "/assets/download/bulk/user",
    BULK_DOWNLOAD_DELETE: (jobId: string) => `/assets/download/bulk/${jobId}`,
  },
  USERS: "/settings/users",
  USER: "/users",
  ROLES: "/settings/roles",
  PERMISSION_SETS: {
    BASE: "/permissions",
    GET: (id: string) => `/permissions/${id}`,
    UPDATE: (id: string) => `/permissions/${id}`,
    DELETE: (id: string) => `/permissions/${id}`,
  },
  API_KEYS: {
    BASE: "/settings/api-keys",
    GET: (id: string) => `/settings/api-keys/${id}`,
    UPDATE: (id: string) => `/settings/api-keys/${id}`,
    DELETE: (id: string) => `/settings/api-keys/${id}`,
  },
  GROUPS: {
    BASE: "/groups",
    GET: (id: string) => `/groups/${id}`,
    UPDATE: (id: string) => `/groups/${id}`,
    DELETE: (id: string) => `/groups/${id}`,
    ADD_MEMBERS: (id: string) => `/groups/${id}/members`,
    REMOVE_MEMBER: (groupId: string, userId: string) =>
      `/groups/${groupId}/members/${userId}`,
  },
  ASSIGNMENTS: {
    USER: {
      BASE: (userId: string) => `/assignments/users/${userId}`,
      REMOVE: (userId: string, permissionSetId: string) =>
        `/assignments/users/${userId}/permission-sets/${permissionSetId}`,
    },
    GROUP: {
      BASE: (groupId: string) => `/assignments/groups/${groupId}`,
      REMOVE: (groupId: string, permissionSetId: string) =>
        `/assignments/groups/${groupId}/permission-sets/${permissionSetId}`,
    },
  },
  DISABLE_USER: (userId: string) => `/users/${userId}/disable`,
  ENABLE_USER: (userId: string) => `/users/${userId}/enable`,
  SYSTEM_SETTINGS: {
    GET: "/settings/system",
    SEARCH: "/settings/system/search",
  },
  FAVORITES: {
    BASE: "/users/favorites",
    DELETE: (itemType: string, itemId: string) =>
      `/users/favorites/${itemType}/${itemId}`,
  },
  COLLECTIONS: {
    BASE: "/collections",
    GET: (id: string) => `/collections/${id}`,
    UPDATE: (id: string) => `/collections/${id}`,
    DELETE: (id: string) => `/collections/${id}`,
    ANCESTORS: (id: string) => `/collections/${id}/ancestors`,
    SHARE: (id: string) => `/collections/${id}/share`,
    UNSHARE: (id: string, userId: string) =>
      `/collections/${id}/share/${userId}`,
    SHARES: (id: string) => `/collections/${id}/shares`,
    SHARED: "/collections/shared",
    ITEMS: (id: string) => `/collections/${id}/items`,
    ASSETS: (id: string) => `/collections/${id}/assets`,
  },
  COLLECTION_TYPES: {
    BASE: "/settings/collection-types",
    GET: (id: string) => `/settings/collection-types/${id}`,
    UPDATE: (id: string) => `/settings/collection-types/${id}`,
    DELETE: (id: string) => `/settings/collection-types/${id}`,
    MIGRATE: (id: string) => `/settings/collection-types/${id}/migrate`,
  },
};
