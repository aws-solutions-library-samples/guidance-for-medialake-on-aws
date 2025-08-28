export const INTEGRATIONS_API = {
  BASE: "/integrations",
  endpoints: {
    GET_INTEGRATIONS: "/integrations",
    GET_INTEGRATION: (id: string) => `/integrations/${id}`,
    CREATE_INTEGRATION: "/integrations",
    UPDATE_INTEGRATION: (id: string) => `/integrations/${id}`,
    UPDATE_STATUS: (id: string) => `/integrations/${id}/status`,
    DELETE_INTEGRATION: (id: string) => `/integrations/${id}`,
  },
} as const;
